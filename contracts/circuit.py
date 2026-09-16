# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

# Circuit — autonomous circuit breaker. This file holds the governance veto
# path (Addendum A §A2.4): READ → DECODE → CONTEXT → JUDGE → GATE → ACT → RECORD.
# Only JUDGE is non-deterministic; every input to it is read from chain and is
# byte-identical for every validator. Validators re-judge independently and
# compare the closed decision fields; free-text reasoning is stored, never
# compared.

import datetime
import json

import genlayer as gl
from genlayer.types import *


ZERO_ADDRESS = Address("0x0000000000000000000000000000000000000000")

NO_ACTION, FLAG, VETO = "NO_ACTION", "FLAG", "VETO"
CONFIDENCE_TOLERANCE = 30       # validators accept the leader's confidence within this band
UNDECODABLE = "<undecodable>"


def _now() -> int:
    raw = gl.message.raw["datetime"].replace("Z", "+00:00")
    return int(datetime.datetime.fromisoformat(raw).timestamp())


def _fmt_arg(a) -> str:
    if isinstance(a, Address):
        return str(a)
    if isinstance(a, bytes):
        return "0x" + a.hex()
    return json.dumps(a)


@gl.storage.allow
class ProposalAssessment:
    proposal_id: u256
    governor: Address
    target: Address
    proposer: Address
    description: str
    # DECODE
    decodable: bool
    method: str
    action: str                 # plain-language: "calls DemoVault.set_owner(0x…)"
    privileged: bool
    known_interface: bool
    # CONTEXT
    proposal_state: str
    turnout_bps: u256
    proposer_power_bps: u256
    proposer_power_age: u256    # seconds since the proposer first held power
    value_at_risk: u256
    # JUDGE
    hostile: bool
    description_matches_calldata: bool
    confidence: u256
    cited_call: str
    reasoning: str
    # GATE / ACT
    verdict: str
    gate_reason: str
    vetoed: bool
    assessed_at: u256
    assessed_by: Address


class ProposalAssessed(gl.chain.Event):
    def __init__(self, proposal_id: u256, verdict: str, /, **blob): ...


class Circuit(gl.contract.Contract):
    deployer: Address
    governor: Address
    high_confidence: u256       # 0-100; at or above → "high confidence"
    quorum_threshold_bps: u256  # Circuit's own turnout floor, independent of the governor's
    proposal_assessments: gl.storage.DynArray[ProposalAssessment]
    latest_for_proposal: gl.storage.TreeMap[u256, u256]   # proposal_id → index + 1

    def __init__(self, governor: str, high_confidence: u256, quorum_threshold_bps: u256):
        if high_confidence > 100 or quorum_threshold_bps > 10_000:
            raise gl.vm.UserError("bad thresholds")
        self.deployer = gl.message.sender_address
        self.governor = Address(governor)
        self.high_confidence = high_confidence
        self.quorum_threshold_bps = quorum_threshold_bps

    # ------------------------------------------------------------------ views
    @gl.public.view
    def get_config(self) -> dict:
        return {
            "deployer": str(self.deployer),
            "governor": str(self.governor),
            "high_confidence": int(self.high_confidence),
            "quorum_threshold_bps": int(self.quorum_threshold_bps),
            "assessment_count": len(self.proposal_assessments),
        }

    def _dump(self, i: int) -> dict:
        a = self.proposal_assessments[i]
        return {
            "index": i,
            "proposal_id": int(a.proposal_id),
            "governor": str(a.governor),
            "target": str(a.target),
            "proposer": str(a.proposer),
            "description": a.description,
            "decodable": a.decodable,
            "method": a.method,
            "action": a.action,
            "privileged": a.privileged,
            "known_interface": a.known_interface,
            "proposal_state": a.proposal_state,
            "turnout_bps": int(a.turnout_bps),
            "proposer_power_bps": int(a.proposer_power_bps),
            "proposer_power_age": int(a.proposer_power_age),
            "value_at_risk": int(a.value_at_risk),
            "hostile": a.hostile,
            "description_matches_calldata": a.description_matches_calldata,
            "confidence": int(a.confidence),
            "cited_call": a.cited_call,
            "reasoning": a.reasoning,
            "verdict": a.verdict,
            "gate_reason": a.gate_reason,
            "vetoed": a.vetoed,
            "assessed_at": int(a.assessed_at),
            "assessed_by": str(a.assessed_by),
        }

    @gl.public.view
    def get_assessment(self, index: u256) -> dict:
        if index >= len(self.proposal_assessments):
            raise gl.vm.UserError("unknown assessment")
        return self._dump(index)

    @gl.public.view
    def get_assessments(self) -> list:
        return [self._dump(i) for i in range(len(self.proposal_assessments))]

    @gl.public.view
    def latest_assessment(self, proposal_id: u256) -> dict:
        idx = self.latest_for_proposal.get(proposal_id, 0)
        if idx == 0:
            return {}
        return self._dump(idx - 1)

    # ------------------------------------------------------------ the path
    @gl.public.write
    def assess_proposal(self, proposal_id: u256) -> str:
        gov = gl.contract.get_at(self.governor)

        # 1. READ — pure on-chain read, byte-identical for every validator.
        p = gov.view().get_proposal(proposal_id)
        target_addr = Address(p["target"])
        target = gl.contract.get_at(target_addr)

        # 2. DECODE — GenVM calldata against the target's declared interface.
        import genlayer.calldata as cd
        decodable, method, args = True, UNDECODABLE, []
        try:
            d = cd.decode(p["calldata"])
            if isinstance(d, dict) and isinstance(d.get(""), str):
                method = d[""]
                args = list(d.get("args", []))
            else:
                decodable = False
        except Exception:
            decodable = False
        iface = target.view(catch_vm_error=True).privileged_methods()
        known_interface = isinstance(iface, list)
        privileged_methods = [str(m) for m in iface] if known_interface else []
        # An undecodable or unknown call aimed at a contract with a privileged
        # surface is treated as privileged: it is a signal, not a gap.
        privileged = known_interface and (not decodable or method in privileged_methods)
        arg_text = ", ".join(_fmt_arg(a) for a in args)
        if decodable:
            action = f"calls {p['target']}.{method}({arg_text})"
        else:
            action = f"sends {len(p['calldata'])} undecodable bytes to {p['target']}"

        # 3. CONTEXT — the facts that make an attack legible.
        total = int(p["total_power"])
        turnout = int(p["for_votes"]) + int(p["against_votes"])
        turnout_bps = turnout * 10_000 // total if total > 0 else 0
        proposer_power_bps = int(p["proposer_power"]) * 10_000 // total if total > 0 else 0
        since = int(p["proposer_power_since"])
        now = _now()
        proposer_power_age = now - since if since > 0 and now > since else 0
        value_at_risk = int(target.balance) if method in ("set_owner", "sweep") or not decodable else 0

        facts = {
            "target": p["target"],
            "decoded_action": action,
            "method": method,
            "calldata_decodable": decodable,
            "target_privileged_methods": privileged_methods,
            "calls_privileged_method": privileged,
            "stated_description": p["description"],
            "proposal_state": p["state"],
            "turnout_bps_of_total_power": turnout_bps,
            "proposer_share_bps_of_total_power": proposer_power_bps,
            "proposer_power_age_seconds": proposer_power_age,
            "value_at_risk": value_at_risk,
        }
        facts_json = json.dumps(facts, sort_keys=True)

        # 4. JUDGE — the only non-deterministic step.
        prompt = (
            "You are auditing a DAO governance proposal for a DeFi vault. The vault's "
            "purpose is to hold user deposits safely; its governor may adjust "
            "parameters. You are given the proposal's stated description and the "
            "DECODED on-chain action its calldata will actually perform, plus context "
            "facts. Judge whether the proposal is hostile to the protocol's purpose "
            "(for example: transferring ownership to an unknown address, sweeping "
            "funds, or an action that does not match what the description claims).\n"
            "Answer with JSON only, exactly these keys:\n"
            '{"hostile": true|false, '
            '"description_matches_calldata": true|false, '
            '"confidence": <integer 0-100, your confidence in the hostile value>, '
            '"cited_call": "<the decoded call you base this on, verbatim>", '
            '"reasoning": "<two sentences max, must reference the decoded call>"}\n'
            "description_matches_calldata is true only if the stated description "
            "honestly describes the decoded action.\n\n"
            f"FACTS:\n{facts_json}\n"
        )

        def leader_fn():
            out = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(out, dict):
                raise gl.vm.UserError("[LLM_ERROR] non-object response")
            hostile = out.get("hostile")
            matches = out.get("description_matches_calldata")
            conf = out.get("confidence")
            if not isinstance(hostile, bool) or not isinstance(matches, bool):
                raise gl.vm.UserError("[LLM_ERROR] verdict fields must be booleans")
            if isinstance(conf, str) and conf.strip().isdigit():
                conf = int(conf)
            if not isinstance(conf, int) or isinstance(conf, bool) or conf < 0 or conf > 100:
                raise gl.vm.UserError("[LLM_ERROR] confidence outside 0-100")
            return {
                "hostile": hostile,
                "matches": matches,
                "confidence": conf,
                "cited_call": str(out.get("cited_call", ""))[:300],
                "reasoning": str(out.get("reasoning", ""))[:600],
            }

        def validator_fn(leader: gl.vm.Result) -> bool:
            if not isinstance(leader, gl.vm.Return):
                return False
            l = leader.calldata
            mine = leader_fn()
            same = (
                bool(l["hostile"]) == mine["hostile"]
                and bool(l["matches"]) == mine["matches"]
                and abs(int(l["confidence"]) - mine["confidence"]) <= CONFIDENCE_TOLERANCE
            )
            print(f"validator: leader hostile={l['hostile']} matches={l['matches']} conf={l['confidence']} | "
                  f"mine hostile={mine['hostile']} matches={mine['matches']} conf={mine['confidence']} -> {same}")
            return same

        j = gl.vm.run_nondet_default(leader_fn, validator_fn)
        hostile = bool(j["hostile"])
        matches = bool(j["matches"])
        confidence = int(j["confidence"])

        # 5. GATE — deterministic.
        high = confidence >= self.high_confidence
        pending = p["state"] in ("ACTIVE", "QUEUED")
        if not pending:
            verdict, reason = NO_ACTION, f"proposal is {p['state']}; nothing to protect"
        elif not privileged:
            verdict, reason = NO_ACTION, "no privileged target"
        elif not hostile:
            if matches:
                verdict, reason = NO_ACTION, "privileged target, judged benign, description matches calldata"
            else:
                verdict, reason = FLAG, "privileged target, judged benign, but description does not match calldata"
        elif not high:
            verdict, reason = FLAG, f"privileged target, hostile at low confidence ({confidence} < {int(self.high_confidence)})"
        elif not matches:
            verdict, reason = VETO, "privileged target, hostile at high confidence, description does NOT match calldata"
        elif turnout_bps < self.quorum_threshold_bps:
            verdict, reason = VETO, f"privileged target, hostile at high confidence, turnout {turnout_bps} bps below threshold {int(self.quorum_threshold_bps)} bps"
        else:
            verdict, reason = FLAG, "privileged target, hostile at high confidence, but description matches calldata and turnout is normal"

        # 6. ACT — only on VETO.
        vetoed = False
        if verdict == VETO:
            gov.emit(on="finalized").veto(proposal_id)
            vetoed = True

        # 7. RECORD — always, including NO_ACTION.
        a = self.proposal_assessments.append_new_get()
        a.proposal_id = proposal_id
        a.governor = self.governor
        a.target = target_addr
        a.proposer = Address(p["proposer"])
        a.description = str(p["description"])
        a.decodable = decodable
        a.method = method
        a.action = action
        a.privileged = privileged
        a.known_interface = known_interface
        a.proposal_state = str(p["state"])
        a.turnout_bps = turnout_bps
        a.proposer_power_bps = proposer_power_bps
        a.proposer_power_age = proposer_power_age
        a.value_at_risk = value_at_risk
        a.hostile = hostile
        a.description_matches_calldata = matches
        a.confidence = confidence
        a.cited_call = str(j["cited_call"])
        a.reasoning = str(j["reasoning"])
        a.verdict = verdict
        a.gate_reason = reason
        a.vetoed = vetoed
        a.assessed_at = now
        a.assessed_by = gl.message.sender_address
        self.latest_for_proposal[proposal_id] = len(self.proposal_assessments)
        ProposalAssessed(proposal_id, verdict, hostile=hostile, matches=matches, confidence=confidence).emit()
        return verdict
