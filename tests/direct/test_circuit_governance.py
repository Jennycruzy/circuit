"""Circuit governance path (§A2.4) in direct mode.

The LLM is mocked per test — what is under test here is READ/DECODE/CONTEXT,
the GATE table, ACT (a veto message to the governor) and RECORD, plus the
validator comparison rule. The model's real judgments are exercised live.
"""
import json
from pathlib import Path

import pytest
from gltest.direct import create_address

from conftest import address_text

CONTRACTS = Path(__file__).parents[2] / "contracts"
T0 = "2026-09-16T20:00:00+00:00"


def at(seconds: int) -> str:
    return f"2026-09-16T20:{seconds // 60:02d}:{seconds % 60:02d}+00:00"


def encode_call(method: str, *args) -> bytes:
    from genlayer import calldata
    from genlayer.types import Address
    # 0x-strings of address length are encoded as calldata addresses, as a real proposer would.
    args = [Address(a) if isinstance(a, str) and a.startswith("0x") and len(a) == 42 else a for a in args]
    return calldata.encode({"": method, "args": args})


def judgment(hostile, matches, confidence, cited="", reasoning="because"):
    # bytes: the direct mock would json.loads a str into a dict, but the v0.3
    # SDK expects the model's raw text and parses it itself.
    return json.dumps({"hostile": hostile, "description_matches_calldata": matches,
                       "confidence": confidence, "cited_call": cited, "reasoning": reasoning}).encode()


@pytest.fixture
def world(chain, direct_vm, direct_deploy, direct_owner, direct_alice, direct_bob):
    direct_vm.warp(T0)
    direct_vm.sender = direct_owner
    vault = chain.deploy(direct_deploy, CONTRACTS / "demo_vault.py", address_text(direct_owner))
    gov = chain.deploy(direct_deploy, CONTRACTS / "demo_governor.py", 60, 120, 1000)
    circuit = chain.deploy(direct_deploy, CONTRACTS / "circuit.py", gov.address, 80, 2000)  # high conf ≥80, turnout floor 20 %
    gov.set_circuit(circuit.address)
    gov.grant_power(address_text(direct_alice), 70)
    gov.grant_power(address_text(direct_bob), 30)
    vault.set_owner(gov.address)
    direct_vm.warp(at(30))
    return dict(vault=vault, gov=gov, circuit=circuit, alice=direct_alice, bob=direct_bob, owner=direct_owner)


def propose(vm, w, method, *args, description, proposer=None, voters=()):
    vm.sender = proposer or w["alice"]
    pid = w["gov"].propose(w["vault"].address, encode_call(method, *args) if method else args[0], 0, description)
    for v in voters:
        vm.sender = v
        w["gov"].vote(pid, True)
    return pid


def test_hostile_mismatch_is_vetoed_and_recorded(chain, direct_vm, world):
    attacker = create_address("attacker")
    pid = propose(direct_vm, world, "set_owner", address_text(attacker), description="Adjust fee parameter", voters=[world["alice"]])
    direct_vm.mock_llm(r"Adjust fee parameter", judgment(True, False, 92, cited="set_owner", reasoning="Description says fee; call transfers ownership."))

    direct_vm.sender = create_address("anyone")
    assert world["circuit"].assess_proposal(pid) == "VETO"

    a = world["circuit"].latest_assessment(pid)
    assert a["action"] == f"calls {world['vault'].address}.set_owner({address_text(attacker)})"
    assert a["privileged"] and a["decodable"] and a["known_interface"]
    assert a["turnout_bps"] == 7000 and a["proposer_power_bps"] == 7000 and a["proposer_power_age"] == 30
    assert a["hostile"] and not a["description_matches_calldata"] and a["confidence"] == 92
    assert a["verdict"] == "VETO" and a["vetoed"] and "does NOT match" in a["gate_reason"]
    assert a["assessed_by"] == address_text(create_address("anyone"))

    # ACT: exactly one veto message to the governor; delivered, it kills the proposal.
    assert len(chain.messages) == 1 and chain.messages[0]["calldata"] == {"": "veto", "args": [pid]}
    assert address_text(chain.messages[0]["address"]) == world["gov"].address
    chain.deliver()
    assert world["gov"].get_proposal(pid)["state"] == "VETOED"
    assert chain.events_named("ProposalAssessed(proposal_id,verdict)")[-1]["verdict"] == "VETO"


def test_benign_matching_proposal_is_no_action(chain, direct_vm, world):
    pid = propose(direct_vm, world, "set_fee_bps", 30, description="Set protocol fee to 0.30%", voters=[world["alice"], world["bob"]])
    direct_vm.mock_llm(r"Set protocol fee", judgment(False, True, 90))
    assert world["circuit"].assess_proposal(pid) == "NO_ACTION"
    a = world["circuit"].latest_assessment(pid)
    assert a["privileged"] and a["verdict"] == "NO_ACTION" and not a["vetoed"] and a["value_at_risk"] == 0
    assert chain.messages == []


def test_gate_table(chain, direct_vm, world):
    attacker = address_text(create_address("attacker"))
    cases = [
        # (hostile, matches, confidence, voters)                → verdict
        ((True, True, 95, [world["alice"], world["bob"]]), "FLAG"),   # hostile, honest description, normal turnout
        ((True, False, 50, [world["alice"]]), "FLAG"),                 # low confidence
        ((False, False, 90, [world["alice"]]), "FLAG"),                # benign but description mismatch
        ((True, True, 95, [world["bob"]]), "VETO"),                    # honest description but turnout 30 % ≥ 20 %… see next
    ]
    # last case: turnout 30 % is above the 20 % floor → FLAG, not VETO
    cases[-1] = ((True, True, 95, [world["bob"]]), "FLAG")
    for i, ((hostile, matches, conf, voters), expected) in enumerate(cases):
        pid = propose(direct_vm, world, "set_owner", attacker, description=f"case {i}", voters=voters)
        direct_vm.clear_mocks()
        direct_vm.mock_llm(rf"case {i}", judgment(hostile, matches, conf))
        assert world["circuit"].assess_proposal(pid) == expected, (i, expected)
    assert chain.messages == []


def test_low_turnout_hostile_is_vetoed_even_with_matching_description(chain, direct_vm, world):
    # Term Labs shape: honest-looking, but passed on near-zero participation.
    whale = create_address("whale")
    direct_vm.sender = world["owner"]
    world["gov"].grant_power(address_text(whale), 10)  # 10 / 110 ≈ 9 % of power
    pid = propose(direct_vm, world, "sweep", address_text(whale), description="Sweep vault funds to 0x" + address_text(whale)[2:], proposer=whale, voters=[whale])
    direct_vm.mock_llm(r"Sweep vault funds", judgment(True, True, 88))
    assert world["circuit"].assess_proposal(pid) == "VETO"
    a = world["circuit"].latest_assessment(pid)
    assert a["turnout_bps"] < 2000 and "turnout" in a["gate_reason"]


def test_unprivileged_target_is_no_action_without_llm_dependence(chain, direct_vm, world):
    # deposit() is not on the vault's privileged list.
    pid = propose(direct_vm, world, "deposit", description="Top up", voters=[world["alice"]])
    direct_vm.mock_llm(r"Top up", judgment(True, False, 99))  # even a hostile judgment cannot veto an unprivileged call
    assert world["circuit"].assess_proposal(pid) == "NO_ACTION"
    assert world["circuit"].latest_assessment(pid)["gate_reason"] == "no privileged target"


def test_undecodable_calldata_is_privileged_signal(chain, direct_vm, world):
    pid = propose(direct_vm, world, None, b"\xde\xad\xbe\xef", description="Routine maintenance", voters=[world["alice"]])
    direct_vm.mock_llm(r"Routine maintenance", judgment(True, False, 85))
    assert world["circuit"].assess_proposal(pid) == "VETO"
    a = world["circuit"].latest_assessment(pid)
    assert not a["decodable"] and a["method"] == "<undecodable>" and a["privileged"]
    assert a["action"].startswith("sends 4 undecodable bytes to ")


def test_settled_proposal_is_no_action(chain, direct_vm, world):
    pid = propose(direct_vm, world, "set_owner", address_text(create_address("x")), description="Adjust fee parameter", voters=[world["alice"]])
    direct_vm.sender = world["circuit"].addr
    world["gov"].veto(pid)
    direct_vm.mock_llm(r"Adjust fee", judgment(True, False, 99))
    assert world["circuit"].assess_proposal(pid) == "NO_ACTION"
    assert "VETOED" in world["circuit"].latest_assessment(pid)["gate_reason"]


def test_llm_output_shape_is_enforced(direct_vm, world):
    pid = propose(direct_vm, world, "set_owner", address_text(create_address("x")), description="Adjust fee parameter", voters=[world["alice"]])
    for bad in ['{"hostile": "yes", "description_matches_calldata": false, "confidence": 90}',
                '{"hostile": true, "description_matches_calldata": false, "confidence": 140}',
                '"just text"']:
        direct_vm.clear_mocks()
        direct_vm.mock_llm(r"Adjust fee", bad.encode())
        with pytest.raises(Exception, match="LLM_ERROR"):
            world["circuit"].assess_proposal(pid)


def test_validator_compares_closed_fields_with_tolerance(direct_vm, world):
    pid = propose(direct_vm, world, "set_owner", address_text(create_address("x")), description="Adjust fee parameter", voters=[world["alice"]])
    direct_vm.mock_llm(r"Adjust fee", judgment(True, False, 90, reasoning="leader wording"))
    world["circuit"].assess_proposal(pid)

    direct_vm.clear_mocks()
    direct_vm.mock_llm(r"Adjust fee", judgment(True, False, 65, reasoning="totally different wording"))
    assert direct_vm.run_validator() is True            # same decision, confidence within 30, reasoning ignored
    direct_vm.clear_mocks()
    direct_vm.mock_llm(r"Adjust fee", judgment(True, False, 55))
    assert direct_vm.run_validator() is False           # confidence drift beyond tolerance
    direct_vm.clear_mocks()
    direct_vm.mock_llm(r"Adjust fee", judgment(True, True, 90))
    assert direct_vm.run_validator() is False           # mismatch flag disagrees
    direct_vm.clear_mocks()
    direct_vm.mock_llm(r"Adjust fee", judgment(False, False, 90))
    assert direct_vm.run_validator() is False           # hostile disagrees
