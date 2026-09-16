# Circuit — Specification Addendum A

Read alongside `SPEC.md`. Everything in the main spec still applies — §1 absolute rules especially.

Adds: **§A2** the governance veto module (the differentiator), **§A3** a real benchmark dataset for §8, **§A4** revised order of work. Do not start §A2 until spike 3 (control call) has succeeded.

## A1. Why this addendum exists

Two other teams have submitted circuit breakers watching an attack **in progress** (threat telemetry, software integrity). The addendum adds the failure mode neither can see.

## A2. The governance veto module

### A2.1 The problem
Term Labs, August 2026: ~$8.5M lost. Near-zero participation let a single wallet pass a proposal seizing the vaults, bypassing the governance delay. The published mitigation — a guardian able to veto during a review window — was not implemented. **A malicious proposal produces no abnormal outflow.** MEASURE sees a healthy protocol. The only way to catch it is to read the proposal and judge its intent.

### A2.2 Why this is the stronger half
The drain detector races a clock it may lose. A timelock is a delay that already exists (hours to days); committee consensus in minutes is comfortably fast. Consensus latency becomes a design fit.

### A2.3 DemoGovernor
Minimal governor, ~80–120 lines (no OpenZeppelin): `propose(targets, calldatas, description)`, `vote`, `queue` (records eta), `veto` (Circuit only, permanent), `execute` (after eta, reverts if vetoed). Test that no other address can veto; test execute reverts when vetoed; events on every transition; short demo timelock with README note that production windows are longer; the governor must control something real (DemoVault parameter/ownership/funds).

### A2.4 `assessProposal`
```
1. READ     proposal from governor — pure on-chain read
2. DECODE   each calldata against known ABIs → plain-language action list;
            unknown selector is a signal, not a gap
3. CONTEXT  turnout share, proposer holdings and recency, privileged targets,
            description-vs-calldata, value at risk
4. JUDGE    hostile? verdict, confidence, cited reasoning naming the decoded call
5. GATE     no privileged target → NO_ACTION
            privileged, low confidence → FLAG
            privileged, high conf, description matches → FLAG
            privileged, high conf, description does NOT match → VETO
            quorum below threshold AND high confidence → VETO
6. ACT      governor.veto(id) on VETO only
7. RECORD   always
```

### A2.5 Description-mismatch signal
First-class field `description_matches_calldata` with the model's reasoning. Subjective, impossible deterministically, legible, and the actual attack pattern.

### A2.6 Easier consensus
Every input is on-chain and byte-identical; only judgment is non-deterministic. If spike 2 fails, the governance module still works — it is the fallback.

### A2.7 Blockers to verify first
Calldata decoding inside GenVM · reading another contract's state · struct/array returns · two control targets from one contract.

## A3. Benchmark dataset
Decurity rescue-window research (rescue-window.decurity.io): ten exploits at 1/5/15/30/60 min. Use as reference and citation, not mirrored. Gives: the achievable window, honest bounding (unwinnable cases), and a false-alarm set. Name TMXTribe (Jan 2026, ~36 h, $1.4M — a decision problem) and Term Labs (Aug 2026) in the README. §A3.3: a governance corpus — real malicious plus many benign proposals; measure the false-veto rate (a wrong veto is governance denial-of-service).

## A4. Revised order of work
1. §3.1 verification + §A2.7. 2. Hello-world live + one nondet tx. 3. Spike 3 first. 4. Spike 2 (if it fails, governance is primary; drain reduced to on-chain-only). 5. DemoVault + DemoGovernor deployed; pause and veto proven. 6. `assess`. 7. `assessProposal`. 8. Equivalence for both paths. 9. Frontend both surfaces. 10. Replay benchmark, both corpora. 11. Real drain and real hostile proposal. 12. README, verification log, video, submission.

Cut order: drain web evidence → benchmark size → evidence UI → bond → graduated levels. **Never cut:** governance veto path, refusal path, description-mismatch check, the real drain, the real hostile proposal, honesty of numbers.

## A5. Frontend additions
Governance watch (decoded actions beside the stated description, turnout vs quorum, timelock remaining, verdict). **The side-by-side is the screen that sells the project.** Proposal detail (full assessment, veto tx). No simulated proposals; the hostile proposal is a real tx from a real second wallet.

## A6. Demo script — four beats
1. The refusal (healthy vault, manufactured panic → NO_ACTION). 2. The benign proposal → NO_ACTION. 3. The hostile proposal → side-by-side → VETO → execute reverts. 4. The drain → PAUSE → receipt.

*Every other circuit breaker reacts after the money starts moving. This one also reads the proposal that would move it.*
