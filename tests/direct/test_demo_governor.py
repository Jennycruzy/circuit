"""DemoGovernor — Addendum A §A2.3 requirements, exercised in direct mode.

Time is controlled with ``direct_vm.warp``; messages the governor emits are
applied to the vault with ``chain.deliver()``, which is what the network does
on finality. The live equivalents are in docs/verification.md.
"""
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
    return calldata.encode({"": method, "args": list(args)})


@pytest.fixture
def world(chain, direct_vm, direct_deploy, direct_owner, direct_alice, direct_bob):
    direct_vm.warp(T0)
    direct_vm.sender = direct_owner
    vault = chain.deploy(direct_deploy, CONTRACTS / "demo_vault.py", address_text(direct_owner))
    gov = chain.deploy(direct_deploy, CONTRACTS / "demo_governor.py", 60, 120, 1000)  # 60 s vote, 120 s timelock, 10 % quorum
    circuit = create_address("circuit")
    gov.set_circuit(address_text(circuit))
    gov.grant_power(address_text(direct_alice), 70)
    gov.grant_power(address_text(direct_bob), 30)
    vault.set_owner(gov.address)  # governor now controls the vault
    return dict(vault=vault, gov=gov, circuit=circuit, alice=direct_alice, bob=direct_bob, owner=direct_owner)


def propose_and_queue(chain, vm, w, method, *args, description="", proposer=None):
    vm.sender = proposer or w["alice"]
    pid = w["gov"].propose(w["vault"].address, encode_call(method, *args), 0, description)
    w["gov"].vote(pid, True)
    vm.warp(at(61))
    w["gov"].queue(pid)
    return pid


def test_config_and_power(world):
    cfg = world["gov"].get_config()
    assert cfg["total_power"] == 100 and cfg["quorum_bps"] == 1000
    assert cfg["circuit"] == address_text(world["circuit"])
    assert world["gov"].voting_power(address_text(world["alice"])) == {"power": 70, "since": 1789588800}


def test_circuit_binding_is_deployer_only_and_one_time(world, direct_vm):
    with direct_vm.prank(world["alice"]), direct_vm.expect_revert("deployer"):
        world["gov"].set_circuit(address_text(world["alice"]))
    direct_vm.sender = world["owner"]
    with direct_vm.expect_revert("already bound"):
        world["gov"].set_circuit(address_text(world["alice"]))


def test_benign_proposal_full_lifecycle_changes_vault(chain, direct_vm, world):
    pid = propose_and_queue(chain, direct_vm, world, "set_fee_bps", 30, description="Set protocol fee to 0.30%")
    p = world["gov"].get_proposal(pid)
    assert p["state"] == "QUEUED" and p["eta"] == 1789588800 + 61 + 120
    assert p["calldata"] == encode_call("set_fee_bps", 30)
    assert p["for_votes"] == 70 and p["proposer_power"] == 70

    with direct_vm.expect_revert("timelock"):
        world["gov"].execute(pid)
    direct_vm.warp(at(61 + 120))
    world["gov"].execute(pid)
    assert world["gov"].get_proposal(pid)["state"] == "EXECUTED"

    assert len(chain.messages) == 1
    assert chain.messages[0]["calldata"] == {"": "set_fee_bps", "args": [30]}
    chain.deliver()  # governor is the vault owner, so this succeeds
    assert world["vault"].get_state()["fee_bps"] == 30
    assert chain.events_named("Executed(proposal_id)")[0]["method"] == "set_fee_bps"


def test_hostile_proposal_reaches_the_vault_without_a_veto(chain, direct_vm, world):
    attacker = create_address("attacker")
    pid = propose_and_queue(chain, direct_vm, world, "set_owner", address_text(attacker), description="Adjust fee parameter")
    direct_vm.warp(at(200))
    world["gov"].execute(pid)
    chain.deliver()
    assert world["vault"].get_state()["owner"] == address_text(attacker)  # the money-moving outcome Circuit must prevent


def test_veto_is_circuit_only(chain, direct_vm, world):
    pid = propose_and_queue(chain, direct_vm, world, "set_owner", address_text(create_address("attacker")))
    for who in (world["owner"], world["alice"], world["bob"]):
        with direct_vm.prank(who), direct_vm.expect_revert("only circuit"):
            world["gov"].veto(pid)
    assert world["gov"].get_proposal(pid)["state"] == "QUEUED"


def test_vetoed_proposal_cannot_execute(chain, direct_vm, world):
    attacker = create_address("attacker")
    pid = propose_and_queue(chain, direct_vm, world, "set_owner", address_text(attacker), description="Adjust fee parameter")
    direct_vm.sender = world["circuit"]
    world["gov"].veto(pid)
    assert world["gov"].get_proposal(pid)["state"] == "VETOED"
    assert chain.events_named("Vetoed(proposal_id)") == [{"proposal_id": pid}]

    direct_vm.warp(at(500))
    direct_vm.sender = world["alice"]
    with direct_vm.expect_revert("vetoed"):
        world["gov"].execute(pid)
    assert chain.messages == []
    assert world["vault"].get_state()["owner"] == world["gov"].address

    direct_vm.sender = world["circuit"]
    with direct_vm.expect_revert("current state"):
        world["gov"].veto(pid)  # veto is terminal, not repeatable


def test_veto_works_while_still_active(chain, direct_vm, world):
    direct_vm.sender = world["alice"]
    pid = world["gov"].propose(world["vault"].address, encode_call("sweep", address_text(world["alice"])), 0, "Rebalance treasury")
    direct_vm.sender = world["circuit"]
    world["gov"].veto(pid)
    direct_vm.sender = world["alice"]
    with direct_vm.expect_revert("not active"):
        world["gov"].vote(pid, True)


def test_quorum_and_majority_defeat(chain, direct_vm, world):
    direct_vm.sender = world["bob"]  # 30 % of power, quorum is 10 %
    pid = world["gov"].propose(world["vault"].address, encode_call("set_fee_bps", 1), 0, "fee")
    world["gov"].vote(pid, False)
    direct_vm.sender = world["alice"]
    world["gov"].vote(pid, True)
    with direct_vm.expect_revert("already voted"):
        world["gov"].vote(pid, True)
    direct_vm.warp(at(61))
    world["gov"].queue(pid)
    assert world["gov"].get_proposal(pid)["state"] == "QUEUED"  # 70 for / 30 against

    # Near-zero turnout below quorum is defeated by the governor itself.
    gov2_quorum = world["gov"]
    direct_vm.sender = world["bob"]
    pid2 = gov2_quorum.propose(world["vault"].address, encode_call("set_fee_bps", 2), 0, "fee")
    direct_vm.warp(at(200))
    gov2_quorum.queue(pid2)
    assert gov2_quorum.get_proposal(pid2)["state"] == "DEFEATED"


def test_proposal_requires_power_and_calldata(direct_vm, world):
    direct_vm.sender = create_address("nobody")
    with direct_vm.expect_revert("no voting power"):
        world["gov"].propose(world["vault"].address, encode_call("set_fee_bps", 1), 0, "x")
    direct_vm.sender = world["alice"]
    with direct_vm.expect_revert("calldata required"):
        world["gov"].propose(world["vault"].address, b"", 0, "x")


def test_undecodable_calldata_is_accepted_but_cannot_execute(chain, direct_vm, world):
    # Circuit must be able to see and flag it; the governor refuses to run it.
    direct_vm.sender = world["alice"]
    pid = world["gov"].propose(world["vault"].address, b"\xde\xad\xbe\xef", 0, "Routine maintenance")
    world["gov"].vote(pid, True)
    direct_vm.warp(at(61))
    world["gov"].queue(pid)
    direct_vm.warp(at(300))
    with pytest.raises(Exception):
        world["gov"].execute(pid)


def test_vault_privileged_surface_is_owner_only(direct_vm, world):
    with direct_vm.prank(world["alice"]), direct_vm.expect_revert("owner"):
        world["vault"].set_fee_bps(5)
    with direct_vm.prank(world["alice"]), direct_vm.expect_revert("owner"):
        world["vault"].set_owner(address_text(world["alice"]))
    assert world["vault"].privileged_methods() == ["set_owner", "set_fee_bps", "sweep", "pause", "restrict"]


def test_cross_contract_view_reads_live_vault_state(chain, world):
    # The harness answers CallContract from the registry — same shape Circuit's READ step uses.
    from genlayer import contract as glc
    from genlayer.types import Address
    state = glc.get_at(Address(world["vault"].address)).view().get_state()
    assert state["owner"] == world["gov"].address
