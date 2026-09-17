"""Circuit drain path (main spec §5.2, §5.5, §5.6) in direct mode.

Web and LLM are mocked per test; the network runs are in docs/verification.md.
Under test: MEASURE, the GATE table, the §5.6 failure rows, ACT messages, the
bond, and the validator comparison rule.
"""
import json
from pathlib import Path

import pytest
from gltest.direct import create_address

from conftest import address_text

CONTRACTS = Path(__file__).parents[2] / "contracts"
T0 = "2026-09-16T20:00:00+00:00"
BOND = 10_000_000_000_000_000
FEED = "https://feed.example/hacks"
PANIC = "https://panic.example/alert"


def at(seconds: int) -> str:
    return f"2026-09-16T20:{seconds // 60:02d}:{seconds % 60:02d}+00:00"


def judge(corr, verdict, conf, cited="fact", reasoning="because"):
    return json.dumps({"corroboration": corr, "verdict": verdict, "exploit_probability": conf, "cited": cited, "reasoning": reasoning}).encode()


def classify(cat, excerpt="…"):
    return json.dumps({"category": cat, "excerpt": excerpt}).encode()


@pytest.fixture
def world(chain, direct_vm, direct_deploy, direct_owner, direct_alice):
    direct_vm.warp(T0)
    direct_vm.sender = direct_owner
    vault = chain.deploy(direct_deploy, CONTRACTS / "demo_vault.py", address_text(direct_owner))
    gov = chain.deploy(direct_deploy, CONTRACTS / "demo_governor.py", 60, 120, 1000)
    circuit = chain.deploy(direct_deploy, CONTRACTS / "circuit.py", gov.address, 80, 2000)
    vault.set_controller(circuit.address)
    # fund the vault: a real deposit through the payable path
    direct_vm.sender = direct_alice
    direct_vm.value = 1_000
    vault.deposit()
    direct_vm.value = 0
    direct_vm._balances[vault.addr] = 1_000  # direct mode does not credit msg.value to the contract balance itself
    direct_vm.sender = direct_owner
    circuit.register_protocol("demovault", vault.address, 2000, 600, json.dumps([FEED, PANIC]),
                              "Funds leaving the vault faster than 20% of balance in ten minutes without a matching governance action is an exploit.")
    # bond for the trigger wallet
    direct_vm.sender = direct_alice
    direct_vm.value = BOND * 2
    circuit.post_bond()
    direct_vm.value = 0
    return dict(vault=vault, gov=gov, circuit=circuit, alice=direct_alice, owner=direct_owner)


def mock_sources(vm, feed_cat="UNRELATED", panic_cat="EXPLOIT_CLAIM", feed_status=200, panic_status=200):
    vm.mock_web(r"feed\.example", {"status": feed_status, "body": "hacks feed body"})
    vm.mock_web(r"panic\.example", {"status": panic_status, "body": "DEMOVAULT IS BEING DRAINED RIGHT NOW"})
    vm.mock_llm(r"(?s)Classify the text.*hacks feed body", classify(feed_cat))
    vm.mock_llm(r"(?s)Classify the text.*DEMOVAULT IS BEING DRAINED", classify(panic_cat, "DEMOVAULT IS BEING DRAINED RIGHT NOW"))


def drain(direct_vm, world, amount):
    # a withdrawal from a second wallet — the vault has no per-user accounting by design
    direct_vm.sender = create_address("attacker")
    world["vault"].withdraw(amount, address_text(create_address("attacker")))
    direct_vm._balances[world["vault"].addr] -= amount


def test_register_measures_baseline_and_is_deployer_only(direct_vm, world):
    p = world["circuit"].get_protocol("demovault")
    assert p["baseline_balance"] == 1_000 and p["baseline_withdrawals"] == 0 and p["evidence_sources"] == [FEED, PANIC]
    with direct_vm.prank(world["alice"]), direct_vm.expect_revert("deployer"):
        world["circuit"].register_protocol("x", world["vault"].address, 2000, 600, "[]", "c")
    direct_vm.sender = world["owner"]
    with direct_vm.expect_revert("already registered"):
        world["circuit"].register_protocol("demovault", world["vault"].address, 2000, 600, "[]", "c")


def test_register_rejects_dead_window_empty_sources_and_empty_baseline(chain, direct_vm, world, direct_deploy):
    direct_vm.sender = world["owner"]
    with direct_vm.expect_revert("window must be positive"):
        world["circuit"].register_protocol(
            "zero-window", world["vault"].address, 2000, 0, json.dumps([FEED]), "c")
    with direct_vm.expect_revert("non-empty"):
        world["circuit"].register_protocol("no-sources", world["vault"].address, 2000, 600, "[]", "c")

    empty_vault = chain.deploy(direct_deploy, CONTRACTS / "demo_vault.py", address_text(world["owner"]))
    direct_vm._balances[empty_vault.addr] = 0
    with direct_vm.expect_revert("balance must be positive"):
        world["circuit"].register_protocol(
            "empty-vault", empty_vault.address, 2000, 600, json.dumps([FEED]), "c")


def test_refusal_manufactured_panic_is_no_action_and_slashes(chain, direct_vm, world):
    # Beat 1: healthy vault, a source screaming "drained". Text alone never acts.
    mock_sources(direct_vm, panic_cat="EXPLOIT_CLAIM")
    direct_vm.mock_llm(r"judgment step", judge("STRONG", "PAUSE", 95, cited="DEMOVAULT IS BEING DRAINED"))  # even a gullible model
    direct_vm.sender = world["alice"]
    assert world["circuit"].assess("demovault") == "ELEVATED"       # strong signal recorded, no action on text
    a = world["circuit"].get_drain_assessments()[-1]
    assert a["outflow_bps"] == 0 and not a["drain_above_threshold"]
    assert a["model_verdict"] == "PAUSE" and a["verdict"] == "ELEVATED" and a["action_taken"] == "none"
    assert chain.messages == []

    direct_vm.clear_mocks(); mock_sources(direct_vm, panic_cat="NO_CLAIM")
    direct_vm.mock_llm(r"judgment step", judge("NONE", "NO_ACTION", 5))
    assert world["circuit"].assess("demovault") == "NO_ACTION"
    a = world["circuit"].get_drain_assessments()[-1]
    assert a["verdict"] == "NO_ACTION" and a["bond_slashed"] == BOND // 2
    assert world["circuit"].bond_of(address_text(world["alice"])) == BOND * 2 - BOND // 2
    assert world["circuit"].get_config()["treasury"] == BOND // 2
    assert world["vault"].get_state()["paused"] is False


def test_real_drain_pauses(chain, direct_vm, world):
    drain(direct_vm, world, 300)   # 30% of the window-start balance
    mock_sources(direct_vm, feed_cat="EXPLOIT_CLAIM")
    direct_vm.mock_llm(r"judgment step", judge("STRONG", "PAUSE", 92, cited="withdrawn_since_window_start: 300"))
    direct_vm.sender = world["alice"]
    assert world["circuit"].assess("demovault") == "PAUSE"
    a = world["circuit"].get_drain_assessments()[-1]
    assert a["outflow"] == 300 and a["outflow_bps"] == 3000 and a["drain_above_threshold"]
    assert a["action_taken"] == "pause" and a["bond_slashed"] == 0
    assert [m["calldata"] for m in chain.messages] == [{"": "pause"}]
    chain.deliver()
    assert world["vault"].get_state()["paused"] is True
    assert chain.events_named("Assessed(protocol_id,verdict)")[-1]["action"] == "pause"


def test_drain_with_low_confidence_restricts_only(chain, direct_vm, world):
    drain(direct_vm, world, 250)
    mock_sources(direct_vm)
    direct_vm.mock_llm(r"judgment step", judge("NONE", "RESTRICT", 55))
    direct_vm.sender = world["alice"]
    assert world["circuit"].assess("demovault") == "RESTRICT"
    assert [m["calldata"] for m in chain.messages] == [{"": "restrict"}]
    chain.deliver()
    s = world["vault"].get_state()
    assert s["restricted"] is True and s["paused"] is False
    direct_vm.sender = world["alice"]; direct_vm.value = 5
    with direct_vm.expect_revert("restricted"):
        world["vault"].deposit()
    direct_vm.value = 0


def test_all_sources_failed_caps_at_restrict(chain, direct_vm, world):
    drain(direct_vm, world, 400)
    direct_vm.mock_web(r"feed\.example", {"status": 503, "body": "down"})
    direct_vm.mock_web(r"panic\.example", {"status": 429, "body": "slow down"})
    direct_vm.mock_llm(r"judgment step", judge("NONE", "PAUSE", 97))
    direct_vm.sender = world["alice"]
    assert world["circuit"].assess("demovault") == "RESTRICT"
    a = world["circuit"].get_drain_assessments()[-1]
    assert sorted(a["sources_failed"]) == sorted([FEED, PANIC]) and a["sources_ok"] == 0
    assert "every evidence source failed" in a["gate_reason"]
    assert [e["category"] for e in a["web_evidence"]] == ["SOURCE_FAILED", "SOURCE_FAILED"]
    assert [m["calldata"] for m in chain.messages] == [{"": "restrict"}]


def test_one_source_failed_is_recorded_not_hidden(chain, direct_vm, world):
    drain(direct_vm, world, 400)
    direct_vm.mock_web(r"feed\.example", {"status": 200, "body": "hacks feed body"})
    direct_vm.mock_llm(r"(?s)Classify the text.*hacks feed body", classify("EXPLOIT_CLAIM"))
    direct_vm.mock_web(r"panic\.example", {"status": 500, "body": ""})
    direct_vm.mock_llm(r"judgment step", judge("STRONG", "PAUSE", 90))
    direct_vm.sender = world["alice"]
    assert world["circuit"].assess("demovault") == "RESTRICT"
    a = world["circuit"].get_drain_assessments()[-1]
    assert a["sources_failed"] == [PANIC] and a["sources_ok"] == 1 and a["action_taken"] == "restrict"


def test_already_paused_records_without_duplicate_action(chain, direct_vm, world):
    direct_vm.sender = world["circuit"].addr
    world["vault"].pause()
    drain_ok = world["vault"].get_state()["paused"]
    assert drain_ok
    mock_sources(direct_vm)
    direct_vm.mock_llm(r"judgment step", judge("NONE", "NO_ACTION", 10))
    direct_vm.sender = world["alice"]
    world["circuit"].assess("demovault")
    a = world["circuit"].get_drain_assessments()[-1]
    assert a["already_paused"] and a["action_taken"] == "already_paused"
    assert chain.messages == []


def test_llm_failure_leaves_no_record(direct_vm, world):
    mock_sources(direct_vm)
    direct_vm.mock_llm(r"judgment step", b'{"corroboration": "MAYBE", "verdict": "PAUSE", "exploit_probability": 90}')
    direct_vm.sender = world["alice"]
    with pytest.raises(Exception, match="LLM_ERROR"):
        world["circuit"].assess("demovault")
    assert world["circuit"].get_drain_assessments() == []
    assert world["circuit"].bond_of(address_text(world["alice"])) == BOND * 2


def test_assess_requires_bond(direct_vm, world):
    mock_sources(direct_vm)
    direct_vm.sender = create_address("freeloader")
    with direct_vm.expect_revert("post a bond"):
        world["circuit"].assess("demovault")
    with direct_vm.expect_revert("post a bond"):
        world["circuit"].assess_proposal(0)


def test_withdraw_bond_emits_transfer(chain, direct_vm, world):
    direct_vm.sender = world["alice"]
    world["circuit"].withdraw_bond()
    assert world["circuit"].bond_of(address_text(world["alice"])) == 0
    m = chain.messages[-1]
    assert address_text(m["address"]) == address_text(world["alice"]) and int(m["value"]) == BOND * 2 and m["calldata"] == {}
    with direct_vm.expect_revert("no bond"):
        world["circuit"].withdraw_bond()


def test_baseline_rolls_once_per_window(direct_vm, world):
    drain(direct_vm, world, 100)
    mock_sources(direct_vm)
    direct_vm.mock_llm(r"judgment step", judge("NONE", "NO_ACTION", 5))
    direct_vm.sender = world["alice"]
    world["circuit"].assess("demovault")
    assert world["circuit"].get_protocol("demovault")["baseline_balance"] == 1_000     # inside the window: unchanged
    direct_vm.warp(at(601))
    direct_vm.sender = world["alice"]
    world["circuit"].assess("demovault")
    p = world["circuit"].get_protocol("demovault")
    assert p["baseline_balance"] == 900 and p["baseline_withdrawals"] == 100          # window elapsed: rolled forward


def test_validator_compares_gate_inputs_only(direct_vm, world):
    drain(direct_vm, world, 300)
    mock_sources(direct_vm, feed_cat="EXPLOIT_CLAIM")
    direct_vm.mock_llm(r"judgment step", judge("STRONG", "PAUSE", 90, reasoning="leader words"))
    direct_vm.sender = world["alice"]
    world["circuit"].assess("demovault")

    def validator_says(corr, verdict, conf):
        direct_vm.clear_mocks(); mock_sources(direct_vm, feed_cat="EXPLOIT_CLAIM")
        direct_vm.mock_llm(r"judgment step", judge(corr, verdict, conf, reasoning="other words"))
        return direct_vm.run_validator()

    assert validator_says("STRONG", "RESTRICT", 85) is True     # model verdict differs: not a gate input
    assert validator_says("STRONG", "PAUSE", 79) is False        # crosses the high threshold (80)
    assert validator_says("WEAK", "PAUSE", 90) is False          # STRONG vs not-STRONG
    # a validator whose own sources fail must reject the leader's different gate input
    direct_vm.clear_mocks(); direct_vm.mock_web(r"example", {"status": 503, "body": ""})
    direct_vm.mock_llm(r"judgment step", judge("STRONG", "PAUSE", 88))
    assert direct_vm.run_validator() is False
    # the live failure shape: leader 2 vs validator 97 must never pass, NONE vs WEAK must
    direct_vm.clear_mocks(); mock_sources(direct_vm)
    direct_vm.mock_llm(r"judgment step", judge("NONE", "NO_ACTION", 2))
    world["circuit"].assess("demovault")
    assert validator_says("WEAK", "NO_ACTION", 4) is True
    assert validator_says("WEAK", "NO_ACTION", 97) is False
