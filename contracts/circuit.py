# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

# Circuit — autonomous circuit breaker. Two detection surfaces:
#   assess(protocol_id)        drain path (main spec §5.2):
#                              MEASURE → GATHER → JUDGE → GATE → ACT → RECORD
#   assess_proposal(id)        governance veto path (Addendum §A2.4):
#                              READ → DECODE → CONTEXT → JUDGE → GATE → ACT → RECORD
# The model proposes; deterministic code decides and acts. Validators re-run
# every non-deterministic step independently and compare only closed decision
# fields; free-text reasoning is stored, never compared. Anyone may trigger an
# assessment, but only with a posted bond, half of which is slashed on
# NO_ACTION so a permissionless trigger cannot be used as spam.

import datetime
import json

import genlayer as gl
from genlayer.types import *


ZERO_ADDRESS = Address("0x0000000000000000000000000000000000000000")

NO_ACTION, FLAG, VETO = "NO_ACTION", "FLAG", "VETO"
ELEVATED, RESTRICT, PAUSE = "ELEVATED", "RESTRICT", "PAUSE"
DRAIN_VERDICTS = (NO_ACTION, ELEVATED, RESTRICT, PAUSE)
CORROBORATION = ("NONE", "WEAK", "STRONG")
SOURCE_CATEGORIES = ("NO_CLAIM", "EXPLOIT_CLAIM", "PAUSE_CLAIM", "UNRELATED", "SOURCE_FAILED")
SOURCE_FAILURE_STATES = ("NONE", "PARTIAL", "ALL")
CONFIDENCE_TOLERANCE = 30       # validators accept the leader's confidence within this band
UNDECODABLE = "<undecodable>"
BOND = 10_000_000_000_000_000   # 0.01 GEN; the mechanism matters more than the number
SLASH_BPS = 5_000               # half the bond on NO_ACTION
MAX_SOURCE_CHARS = 30_000       # prompt budget per source (measured: 346 KB fetches fine)


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


@gl.storage.allow
class Protocol:
    protocol_id: str
    target: Address
    drain_threshold_bps: u256   # outflow over the window that counts as a drain
    window_s: u256              # baseline refreshes at most once per window
    baseline_balance: u256
    baseline_withdrawals: u256
    baseline_at: u256
    evidence_sources: str       # JSON list of URLs — real, uncontrolled, best-effort
    criteria: str               # plain language: what counts as an exploit here
    registered_at: u256


@gl.storage.allow
class Assessment:
    protocol_id: str
    assessed_at: u256
    caller: Address
    # MEASURE
    balance: u256
    baseline_balance: u256
    outflow: u256               # withdrawals since baseline
    outflow_bps: u256           # of baseline balance
    drain_above_threshold: bool
    already_paused: bool
    # GATHER
    web_evidence: str           # JSON per source: url, status, category, excerpt, error
    sources_failed: str         # JSON list of URLs — named, never hidden
    sources_total: u256
    sources_ok: u256
    # JUDGE
    corroboration: str          # NONE | WEAK | STRONG
    model_verdict: str          # what the model proposed
    confidence: u256
    cited: str
    reasoning: str
    # GATE / ACT
    verdict: str                # NO_ACTION | ELEVATED | RESTRICT | PAUSE
    gate_reason: str
    action_taken: str           # none | restrict | pause | already_paused
    bond_slashed: u256


class Assessed(gl.chain.Event):
    def __init__(self, protocol_id: str, verdict: str, /, **blob): ...


class ProposalAssessed(gl.chain.Event):
    def __init__(self, proposal_id: u256, verdict: str, /, **blob): ...


class Circuit(gl.contract.Contract):
    deployer: Address
    governor: Address
    high_confidence: u256       # 0-100; at or above → "high confidence"
    quorum_threshold_bps: u256  # Circuit's own turnout floor, independent of the governor's
    proposal_assessments: gl.storage.DynArray[ProposalAssessment]
    latest_for_proposal: gl.storage.TreeMap[u256, u256]   # proposal_id → index + 1
    watchlist: gl.storage.TreeMap[str, Protocol]
    assessments: gl.storage.DynArray[Assessment]
    bonds: gl.storage.TreeMap[Address, u256]
    treasury: u256              # slashed bonds

    def __init__(self, governor: str, high_confidence: u256, quorum_threshold_bps: u256):
        if high_confidence == 0 or high_confidence > 100 or quorum_threshold_bps > 10_000:
            raise gl.vm.UserError("bad thresholds")
        self.deployer = gl.message.sender_address
        self.governor = Address(governor)
        self.high_confidence = high_confidence
        self.quorum_threshold_bps = quorum_threshold_bps
        self.treasury = 0

    # ------------------------------------------------------------------ views
    @gl.public.view
    def get_config(self) -> dict:
        return {
            "deployer": str(self.deployer),
            "governor": str(self.governor),
            "high_confidence": int(self.high_confidence),
            "quorum_threshold_bps": int(self.quorum_threshold_bps),
            "proposal_assessment_count": len(self.proposal_assessments),
            "assessment_count": len(self.assessments),
            "bond": BOND,
            "slash_bps": SLASH_BPS,
            "treasury": int(self.treasury),
            "now": _now(),
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
        self._require_bond()
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
        # A target that cannot answer this view is opaque. Do not turn that
        # failure into an implicit "unprivileged" result: the proposal still
        # needs an operator-visible decision, but Circuit cannot safely veto it
        # without knowing the target's surface.
        try:
            iface = target.view(catch_vm_error=True).privileged_methods()
        except Exception:
            iface = None
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
            lc, mc, high = int(l["confidence"]), mine["confidence"], int(self.high_confidence)
            same = (
                bool(l["hostile"]) == mine["hostile"]
                and bool(l["matches"]) == mine["matches"]
                and (lc >= high) == (mc >= high)          # the gate's threshold, compared exactly
                and abs(lc - mc) <= CONFIDENCE_TOLERANCE
            )
            print(f"validator: leader hostile={l['hostile']} matches={l['matches']} conf={l['confidence']} | "
                  f"mine hostile={mine['hostile']} matches={mine['matches']} conf={mine['confidence']} -> {same}")
            return same

        if not known_interface:
            # An opaque target is a deterministic review failure. Avoid
            # spending a nondeterministic round on a call whose safety surface
            # is unknown; the explicit FLAG below is the only safe outcome.
            j = {
                "hostile": False,
                "matches": False,
                "confidence": 0,
                "cited_call": "",
                "reasoning": "target did not expose a readable privileged interface",
            }
        else:
            j = gl.vm.run_nondet_default(leader_fn, validator_fn)
        hostile = bool(j["hostile"])
        matches = bool(j["matches"])
        confidence = int(j["confidence"])

        # 5. GATE — deterministic.
        high = confidence >= self.high_confidence
        pending = p["state"] in ("ACTIVE", "QUEUED")
        if not pending:
            verdict, reason = NO_ACTION, f"proposal is {p['state']}; nothing to protect"
        elif not known_interface:
            verdict, reason = FLAG, "target privileged interface unavailable; manual review required"
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
        self._settle_bond(verdict == NO_ACTION)
        ProposalAssessed(proposal_id, verdict, hostile=hostile, matches=matches, confidence=confidence).emit()
        return verdict

    # ================================================================ bond
    @gl.public.write.payable
    def post_bond(self) -> None:
        if gl.message.value <= 0:
            raise gl.vm.UserError("bond value must be positive")
        sender = gl.message.sender_address
        self.bonds[sender] = self.bonds.get(sender, 0) + gl.message.value

    @gl.public.write
    def withdraw_bond(self) -> None:
        sender = gl.message.sender_address
        amount = self.bonds.get(sender, 0)
        if amount <= 0:
            raise gl.vm.UserError("no bond to withdraw")
        self.bonds[sender] = 0
        gl.chain.Account(sender).emit_transfer(amount, on="finalized")

    @gl.public.view
    def bond_of(self, holder: str) -> int:
        return int(self.bonds.get(Address(holder), 0))

    def _require_bond(self) -> None:
        if self.bonds.get(gl.message.sender_address, 0) < BOND:
            raise gl.vm.UserError("post a bond of at least " + str(BOND) + " before assessing")

    def _settle_bond(self, slash: bool) -> int:
        if not slash:
            return 0
        sender = gl.message.sender_address
        cut = BOND * SLASH_BPS // 10_000
        self.bonds[sender] = self.bonds.get(sender, 0) - cut
        self.treasury = self.treasury + cut
        return cut

    # ============================================================ watchlist
    @gl.public.write
    def register_protocol(self, protocol_id: str, target: str, drain_threshold_bps: u256,
                          window_s: u256, evidence_sources: str, criteria: str) -> None:
        if gl.message.sender_address != self.deployer:
            raise gl.vm.UserError("only the deployer may register protocols")
        if protocol_id in self.watchlist:
            raise gl.vm.UserError("protocol already registered")
        if drain_threshold_bps == 0 or drain_threshold_bps > 10_000:
            raise gl.vm.UserError("bad threshold")
        if window_s == 0:
            raise gl.vm.UserError("window must be positive")
        try:
            srcs = json.loads(evidence_sources)
        except Exception:
            raise gl.vm.UserError("evidence_sources must be a JSON list of URLs")
        if (not isinstance(srcs, list) or not srcs
                or not all(isinstance(u, str) and u.strip() for u in srcs)
                or not all(u.startswith("http://") or u.startswith("https://") for u in srcs)):
            raise gl.vm.UserError("evidence_sources must be a non-empty HTTP(S) URL list")
        if not isinstance(criteria, str) or not criteria.strip():
            raise gl.vm.UserError("criteria must be non-empty")
        t = Address(target)
        target_contract = gl.contract.get_at(t)
        try:
            state = target_contract.view().get_state()       # must be readable now, or we cannot watch it
            iface = target_contract.view(catch_vm_error=True).privileged_methods()
        except Exception:
            raise gl.vm.UserError("target must expose get_state and privileged_methods")
        if not isinstance(state, dict) or not all(k in state for k in ("balance", "total_withdrawals", "paused", "restricted")):
            raise gl.vm.UserError("target get_state is incomplete")
        methods = [str(m) for m in iface] if isinstance(iface, list) else []
        if "pause" not in methods or "restrict" not in methods:
            raise gl.vm.UserError("target must expose pause and restrict")
        baseline_balance = int(state["balance"])
        baseline_withdrawals = int(state["total_withdrawals"])
        if baseline_balance <= 0:
            raise gl.vm.UserError("target balance must be positive")
        if baseline_withdrawals < 0:
            raise gl.vm.UserError("target withdrawals cannot be negative")
        p = self.watchlist.get_or_insert_default(protocol_id)
        p.protocol_id = protocol_id
        p.target = t
        p.drain_threshold_bps = drain_threshold_bps
        p.window_s = window_s
        p.baseline_balance = baseline_balance
        p.baseline_withdrawals = baseline_withdrawals
        p.baseline_at = _now()
        p.evidence_sources = evidence_sources
        p.criteria = criteria
        p.registered_at = p.baseline_at

    @gl.public.write
    def update_protocol(self, protocol_id: str, target: str, drain_threshold_bps: u256,
                        window_s: u256, evidence_sources: str, criteria: str,
                        reset_baseline: bool) -> None:
        if gl.message.sender_address != self.deployer:
            raise gl.vm.UserError("only the deployer may update protocols")
        if protocol_id not in self.watchlist:
            raise gl.vm.UserError("unknown protocol")
        if drain_threshold_bps == 0 or drain_threshold_bps > 10_000:
            raise gl.vm.UserError("bad threshold")
        if window_s == 0:
            raise gl.vm.UserError("window must be positive")
        try:
            srcs = json.loads(evidence_sources)
        except Exception:
            raise gl.vm.UserError("evidence_sources must be a JSON list of URLs")
        if (not isinstance(srcs, list) or not srcs
                or not all(isinstance(u, str) and u.strip() for u in srcs)
                or not all(u.startswith("http://") or u.startswith("https://") for u in srcs)):
            raise gl.vm.UserError("evidence_sources must be a non-empty HTTP(S) URL list")
        if not isinstance(criteria, str) or not criteria.strip():
            raise gl.vm.UserError("criteria must be non-empty")
        t = Address(target)
        target_contract = gl.contract.get_at(t)
        try:
            state = target_contract.view().get_state()
            iface = target_contract.view(catch_vm_error=True).privileged_methods()
        except Exception:
            raise gl.vm.UserError("target must expose get_state and privileged_methods")
        if not isinstance(state, dict) or not all(k in state for k in ("balance", "total_withdrawals", "paused", "restricted")):
            raise gl.vm.UserError("target get_state is incomplete")
        methods = [str(m) for m in iface] if isinstance(iface, list) else []
        if "pause" not in methods or "restrict" not in methods:
            raise gl.vm.UserError("target must expose pause and restrict")
        baseline_balance = int(state["balance"])
        baseline_withdrawals = int(state["total_withdrawals"])
        if baseline_balance <= 0:
            raise gl.vm.UserError("target balance must be positive")
        if baseline_withdrawals < 0:
            raise gl.vm.UserError("target withdrawals cannot be negative")
        p = self.watchlist[protocol_id]
        if t != p.target and not reset_baseline:
            raise gl.vm.UserError("target changes require reset_baseline=true")
        p.target = t
        p.drain_threshold_bps = drain_threshold_bps
        p.window_s = window_s
        p.evidence_sources = evidence_sources
        p.criteria = criteria
        if reset_baseline:
            p.baseline_balance = baseline_balance
            p.baseline_withdrawals = baseline_withdrawals
            p.baseline_at = _now()
    @gl.public.view
    def get_protocol(self, protocol_id: str) -> dict:
        if protocol_id not in self.watchlist:
            raise gl.vm.UserError("unknown protocol")
        p = self.watchlist[protocol_id]
        return {
            "protocol_id": p.protocol_id, "target": str(p.target),
            "drain_threshold_bps": int(p.drain_threshold_bps), "window_s": int(p.window_s),
            "baseline_balance": int(p.baseline_balance), "baseline_withdrawals": int(p.baseline_withdrawals),
            "baseline_at": int(p.baseline_at), "evidence_sources": json.loads(p.evidence_sources),
            "criteria": p.criteria, "registered_at": int(p.registered_at),
        }

    def _dump_assessment(self, i: int) -> dict:
        a = self.assessments[i]
        return {
            "index": i, "protocol_id": a.protocol_id, "assessed_at": int(a.assessed_at), "caller": str(a.caller),
            "balance": int(a.balance), "baseline_balance": int(a.baseline_balance), "outflow": int(a.outflow),
            "outflow_bps": int(a.outflow_bps), "drain_above_threshold": a.drain_above_threshold,
            "already_paused": a.already_paused,
            "web_evidence": json.loads(a.web_evidence), "sources_failed": json.loads(a.sources_failed),
            "sources_total": int(a.sources_total), "sources_ok": int(a.sources_ok),
            "corroboration": a.corroboration, "model_verdict": a.model_verdict, "confidence": int(a.confidence),
            "cited": a.cited, "reasoning": a.reasoning,
            "verdict": a.verdict, "gate_reason": a.gate_reason, "action_taken": a.action_taken,
            "bond_slashed": int(a.bond_slashed),
        }

    @gl.public.view
    def get_drain_assessment(self, index: u256) -> dict:
        if index >= len(self.assessments):
            raise gl.vm.UserError("unknown assessment")
        return self._dump_assessment(index)

    @gl.public.view
    def get_drain_assessments(self) -> list:
        return [self._dump_assessment(i) for i in range(len(self.assessments))]

    # =========================================================== drain path
    @gl.public.write
    def assess(self, protocol_id: str) -> str:
        self._require_bond()
        if protocol_id not in self.watchlist:
            raise gl.vm.UserError("unknown protocol")
        p = self.watchlist[protocol_id]
        target = gl.contract.get_at(p.target)
        now = _now()

        # 1. MEASURE — primary evidence. A revert here aborts: no judgment
        #    without the on-chain facts. No model, no web.
        state = target.view().get_state()
        balance = int(target.balance)
        withdrawals = int(state["total_withdrawals"])
        already_paused = bool(state["paused"])
        baseline_balance = int(p.baseline_balance)
        outflow = max(0, withdrawals - int(p.baseline_withdrawals))
        outflow_bps = outflow * 10_000 // baseline_balance if baseline_balance > 0 else 0
        drain_above = outflow_bps >= int(p.drain_threshold_bps)
        elapsed = max(0, now - int(p.baseline_at))
        facts = {
            "protocol_id": protocol_id,
            "target": str(p.target),
            "balance_now": balance,
            "balance_at_window_start": baseline_balance,
            "withdrawn_since_window_start": outflow,
            "outflow_bps_of_window_start_balance": outflow_bps,
            "drain_threshold_bps": int(p.drain_threshold_bps),
            "drain_above_threshold": drain_above,
            "window_seconds": int(p.window_s),
            "seconds_since_window_start": elapsed,
            "already_paused": already_paused,
        }
        facts_json = json.dumps(facts, sort_keys=True)
        sources = [str(u) for u in json.loads(p.evidence_sources)]
        criteria = p.criteria

        # 2+3. GATHER + JUDGE — one nondet block. Each source is fetched and
        #      classified; a failure is data, never a substitute. Then one
        #      judgment over measured facts + evidence excerpts.
        def fetch_one(url: str) -> dict:
            try:
                res = gl.nondet.web.get(url)
                status = int(getattr(res, "status", getattr(res, "status_code", 0)))
                body = res.body.decode("utf-8", errors="replace")
            except Exception as e:
                return {"url": url, "status": 0, "category": "SOURCE_FAILED",
                        "error": (type(e).__name__ + ": " + str(e))[:160], "excerpt": ""}
            if status >= 400:
                return {"url": url, "status": status, "category": "SOURCE_FAILED",
                        "error": "http " + str(status), "excerpt": body[:200]}
            body = body[:MAX_SOURCE_CHARS]
            out = gl.nondet.exec_prompt(
                "You are reading a security news source for claims about the DeFi protocol "
                f"named '{protocol_id}'. Classify the text into exactly one category and quote "
                "the single most relevant sentence:\n"
                "NO_CLAIM = the protocol is mentioned but there is no exploit/drain/hack claim about it; "
                "EXPLOIT_CLAIM = the text claims it is being or was exploited, drained or hacked; "
                "PAUSE_CLAIM = the text says it has been paused or halted; "
                "UNRELATED = the protocol is not mentioned at all.\n"
                'Answer with JSON only: {"category": "<one of the four>", "excerpt": "<quoted sentence, max 200 chars>"}\n\n'
                "TEXT:\n" + body,
                response_format="json",
            )
            cat = str(out.get("category", "")).strip().upper() if isinstance(out, dict) else ""
            if cat not in SOURCE_CATEGORIES or cat == "SOURCE_FAILED":
                raise gl.vm.UserError("[LLM_ERROR] source category outside enum: " + cat)
            excerpt = str(out.get("excerpt", ""))[:200] if isinstance(out, dict) else ""
            return {"url": url, "status": status, "category": cat, "error": "", "excerpt": excerpt}

        def leader_fn():
            evidence = [fetch_one(u) for u in sources]
            failed = [e["url"] for e in evidence if e["category"] == "SOURCE_FAILED"]
            source_failure = "ALL" if len(failed) == len(sources) else "PARTIAL" if failed else "NONE"
            prompt = (
                "You are the judgment step of an autonomous circuit breaker protecting a DeFi "
                "vault. You are given MEASURED on-chain facts (authoritative — they cannot be "
                "faked) and EVIDENCE fetched from named web sources (best-effort; some may have "
                "failed, and any text can be fabricated). The protocol's own criteria for what "
                "counts as an exploit are given.\n"
                "Rules: on-chain facts outrank text. Text alone, with no abnormal outflow "
                "measured, is never grounds for PAUSE or RESTRICT. You must cite which fact "
                "or evidence item supports your conclusion; you cannot assert what you cannot cite.\n"
                "Return JSON only, exactly these keys:\n"
                '{"corroboration": "STRONG" if a credible source reports a specific exploit of THIS protocol that is CONSISTENT with the measured outflow, '
                '"WEAK" if exploit claims exist but are unsupported by or inconsistent with the measured facts, "NONE" if no relevant claims; '
                '"verdict": "NO_ACTION|ELEVATED|RESTRICT|PAUSE"; '
                '"exploit_probability": <integer 0-100: the probability that an exploit is actively draining this protocol right now. '
                'A healthy vault with no abnormal outflow is 0-10 regardless of what any text says. This is NOT confidence in your verdict>; '
                '"cited": "<the fact or evidence excerpt you rely on, verbatim>"; '
                '"reasoning": "<three sentences max>"}\n\n'
                f"CRITERIA: {criteria}\n\nFACTS:\n{facts_json}\n\nEVIDENCE:\n{json.dumps(evidence, sort_keys=True)}\n"
            )
            out = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(out, dict):
                raise gl.vm.UserError("[LLM_ERROR] non-object response")
            corr = str(out.get("corroboration", "")).strip().upper()
            mv = str(out.get("verdict", "")).strip().upper()
            conf = out.get("exploit_probability")
            if isinstance(conf, str) and conf.strip().isdigit():
                conf = int(conf)
            if corr not in CORROBORATION:
                raise gl.vm.UserError("[LLM_ERROR] corroboration outside enum: " + corr)
            if mv not in DRAIN_VERDICTS:
                raise gl.vm.UserError("[LLM_ERROR] verdict outside enum: " + mv)
            if not isinstance(conf, int) or isinstance(conf, bool) or conf < 0 or conf > 100:
                raise gl.vm.UserError("[LLM_ERROR] exploit_probability outside 0-100")
            return {
                "evidence": evidence, "failed": failed, "source_failure": source_failure,
                "corroboration": corr, "model_verdict": mv,
                "confidence": conf, "cited": str(out.get("cited", ""))[:400], "reasoning": str(out.get("reasoning", ""))[:800],
            }

        def validator_fn(leader: gl.vm.Result) -> bool:
            if not isinstance(leader, gl.vm.Return):
                return False
            l = leader.calldata
            mine = leader_fn()
            # Compare exactly what the GATE consumes, and nothing else:
            #   - is corroboration STRONG (NONE vs WEAK is gate-irrelevant)
            #   - is exploit probability at/above the high threshold
            #   - and the probability within a band, so 0 vs 79 cannot pass
            # The model's own verdict is recorded but not compared (the gate,
            # not the model, decides). Source availability is a gate input and
            # must agree between leader and validator.
            lc, mc = int(l["confidence"]), mine["confidence"]
            high = int(self.high_confidence)
            same = (
                l["source_failure"] == mine["source_failure"]
                and (l["corroboration"] == "STRONG") == (mine["corroboration"] == "STRONG")
                and (lc >= high) == (mc >= high)
                and abs(lc - mc) <= CONFIDENCE_TOLERANCE
            )
            print(f"validator: leader corr={l['corroboration']} v={l['model_verdict']} conf={l['confidence']} failed={len(l['failed'])} ({l['source_failure']}) | "
                  f"mine corr={mine['corroboration']} v={mine['model_verdict']} conf={mine['confidence']} failed={len(mine['failed'])} ({mine['source_failure']}) -> {same}")
            return same

        j = gl.vm.run_nondet_default(leader_fn, validator_fn)
        corroboration = str(j["corroboration"])
        confidence = int(j["confidence"])
        failed = list(j["failed"])
        source_failure = str(j["source_failure"])
        sources_ok = len(sources) - len(failed)

        # 4. GATE — deterministic; the model's verdict is recorded but the
        #    gate decides. Text alone never reaches an action.
        high = confidence >= self.high_confidence
        if not drain_above:
            if corroboration == "STRONG":
                verdict, reason = ELEVATED, "outflow below threshold; strong web signal recorded, no action on text alone"
            else:
                verdict, reason = NO_ACTION, "outflow below threshold and no strong corroboration"
        elif not high:
            verdict, reason = RESTRICT, f"outflow above threshold; confidence {confidence} below {int(self.high_confidence)}"
        elif source_failure != "NONE":
            if source_failure == "ALL":
                reason = "every evidence source failed; verdict capped at RESTRICT"
            else:
                reason = "one or more evidence sources failed; PAUSE requires all sources"
            verdict = RESTRICT
        else:
            verdict, reason = PAUSE, f"outflow above threshold at high confidence ({confidence})"

        # 5. ACT — only the gate reaches the target.
        action = "none"
        if already_paused:
            action = "already_paused"
        elif verdict == PAUSE:
            target.emit(on="finalized").pause()
            action = "pause"
        elif verdict == RESTRICT and not bool(state.get("restricted", False)):
            target.emit(on="finalized").restrict()
            action = "restrict"

        # 6. RECORD — always, including NO_ACTION. Then roll the baseline
        #    forward at most once per window.
        slashed = self._settle_bond(verdict == NO_ACTION)
        a = self.assessments.append_new_get()
        a.protocol_id = protocol_id
        a.assessed_at = now
        a.caller = gl.message.sender_address
        a.balance = balance
        a.baseline_balance = baseline_balance
        a.outflow = outflow
        a.outflow_bps = outflow_bps
        a.drain_above_threshold = drain_above
        a.already_paused = already_paused
        a.web_evidence = json.dumps(j["evidence"], sort_keys=True)
        a.sources_failed = json.dumps(failed)
        a.sources_total = len(sources)
        a.sources_ok = sources_ok
        a.corroboration = corroboration
        a.model_verdict = str(j["model_verdict"])
        a.confidence = confidence
        a.cited = str(j["cited"])
        a.reasoning = str(j["reasoning"])
        a.verdict = verdict
        a.gate_reason = reason
        a.action_taken = action
        a.bond_slashed = slashed
        if elapsed >= int(p.window_s) and balance > 0:
            p.baseline_balance = balance
            p.baseline_withdrawals = withdrawals
            p.baseline_at = now
        Assessed(protocol_id, verdict, confidence=confidence, outflow_bps=outflow_bps, action=action).emit()
        return verdict
