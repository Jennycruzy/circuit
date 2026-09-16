# Circuit — Engineering Specification

**An autonomous exploit detector and kill switch, built as a GenLayer Intelligent Contract.**

**Target:** GenLayer Agent Tank Hackathon
**Working name:** Circuit

> Hand this document to the engineering agent as a standing brief.
> Read §1 before every working session.
> **Verify every technical claim in this document against the live GenLayer docs
> before implementing it.** The docs are authoritative; this spec is a plan.

---

## 1. Standing instructions to the engineering agent

### 1.1 Who you are

You are operating as a **staff-level engineer with 10+ years of production
experience**. You switch between three disciplines and you name which one you're in when the choice matters:

| Discipline | The standard you hold |
|---|---|
| **Protocol engineer** | You write invariants before implementations. You assume every external call is hostile and every data source can vanish mid-execution. A security tool that fires wrongly is worse than no security tool. |
| **LLM systems engineer** | An unconstrained model will confidently assert things it cannot support. Ground every judgment in retrieved evidence, make refusal a first-class output, never let a model's confidence stand in for a measurement. |
| **Frontend engineer** | A judge opening the demo URL cold must understand what they're looking at inside thirty seconds. |

### 1.2 Absolute rules

**1. No mocks. No stubs. No hardcoded values. No fabricated evidence. No
simulated LLM responses. No placeholder data.** Every number displayed, every verdict rendered, every piece of evidence cited comes from a live contract call, a live web fetch, or a real model inference executed by real validators. Forbidden: a hardcoded "exploit detected" path; canned LLM output; seeded evidence presented as fetched; a fake vault balance, fake drain, or scripted attack that isn't a real transaction; a developer-written verdict displayed as the contract's. If something cannot be built for real, it is not built, and its absence is stated plainly in the README.

**2. Refusal is the primary success case.** `NO_ACTION` verdicts get the same code paths, test coverage, on-chain record, and UI prominence as `EXPLOIT_CONFIRMED`. Build the refusal path first.

**3. Evidence hierarchy is non-negotiable: on-chain state first, web second.** Judgment anchored on measured on-chain facts; web sources only interpret them. A design where a tweet alone can trigger action will be attacked.

**4. Verify against the live docs before implementing.** If this spec and the docs disagree, the docs win — say so in `PROGRESS.md`.

**5. Never claim a capability you have not executed.**

**6. Tests ship in the same commit as the code.**

**7. When blocked, stop and report.** If a web source is unreachable, the correct behaviour is a degraded-confidence verdict, not substituted data.

### 1.3 Working agreement

- Maintain `PROGRESS.md`: done / next / blocked / doc-divergences found.
- Propose the interface before implementing.
- After each significant change, run everything and report honestly.
- Nothing is "done" until executed end to end against the live network at least once.

---

## 2. What this is, in plain terms

When a DeFi protocol is exploited, funds drain over minutes while the team sleeps. Stopping it today means humans and a multisig; that takes hours. **Circuit watches instead.** It reads the protocol's own on-chain state — is value leaving at an abnormal rate — and what security researchers publish, judges whether this is an active exploit, normal volatility, or manufactured panic, and on a confirmed exploit pauses the protocol itself.

**Why only GenLayer.** One model cannot make this call: a single fabricated "PROTOCOL X IS DRAINING" post would freeze a healthy protocol. GenLayer runs the judgment across a random committee of validators on different LLMs with appeals behind it. The existing alternative is a multisig pause guardian — centralised, slow, awake only when its humans are.

---

## 3. Verification — before writing any contract

Record every result in `docs/verification.md` with timestamps.

### 3.1 Documentation verification
- Non-deterministic block syntax (LLM calls, web fetches).
- Equivalence Principle modes; exact API for non-comparative validation.
- Web access constraints — timeouts, size limits, schemes, arbitrary URLs.
- Can an IC call a Solidity contract on GenLayer Chain (Ghost contract)? Exact mechanism.
- Deployment path — Studio, CLI, Skills plugin.
- Gas/cost limits bounding fetches and LLM calls per transaction.
- Reading contract state from a frontend — library, method.

Any answer that contradicts this spec overrides this spec.

### 3.2 Environment verification
- Install the GenLayer Skills plugin; fall back to CLI and record why.
- Deploy hello-world to the live network on day one.
- Execute one non-deterministic call in a real transaction; record the hash.
- Read that contract's state from a browser.

### 3.3 Feasibility spikes
- **Web fetch reliability.** Fetch each intended source ten times over an hour; anything below ~80% is optional evidence.
- **Consensus on non-deterministic input.** Throwaway contract fetching a live changing page and judging it. Does it reach consensus? Highest-risk unknown.
- **Ghost → Solidity call.** IC pauses a trivial pausable contract, end to end.

If spike two fails, the contract reads only on-chain state and web evidence is dropped or caller-supplied.

---

## 4. Architecture

```
Frontend (reads GenLayer state directly): live assessments · verdicts · evidence · trigger
Circuit — Intelligent Contract: watchlist · assess() gather→judge→record→act · history · bonds
DemoVault — pausable target: deposits · withdrawals · pause() callable only by Circuit
```

**Everything on one chain. No bridge.** (§4.1: bridge finality fights the product, multiplies failure modes, and isn't needed to prove the thesis. State this in the README; put cross-chain in the roadmap.)

---

## 5. The Intelligent Contract

### 5.1 Shape

```python
class Circuit(gl.Contract):
    watchlist: TreeMap[str, Protocol]
    assessments: DynArray[Assessment]
    bonds: TreeMap[Address, u256]

@dataclass
class Protocol:
    protocol_id: str
    target: Address            # the pausable contract
    baseline_balance: u256     # rolling reference
    drain_threshold_bps: u32   # e.g. 2000 = 20% in the window
    window_blocks: u32
    evidence_sources: list[str]
    criteria: str              # plain-language, what counts as an exploit here
    paused: bool

@dataclass
class Assessment:
    protocol_id: str
    block: u256
    verdict: str               # NO_ACTION | ELEVATED | RESTRICT | PAUSE
    confidence: u8             # 0–100
    onchain_evidence: str      # measured facts
    web_evidence: str          # what was fetched, per source
    sources_failed: list[str]  # named explicitly, never hidden
    reasoning: str             # the model's cited argument
    action_taken: str
    caller: Address
```

### 5.2 The assessment pipeline

```
1. MEASURE  (deterministic)  balance, delta over window, drain rate. Always succeeds.
2. GATHER   (non-det, degradable)  fetch each source; record successes AND failures.
            A failed source lowers confidence; never blocks; never substituted.
3. JUDGE    (non-det, LLM)  verdict, confidence, cited reasoning. Must cite evidence.
4. GATE     (deterministic)
   drain below threshold AND no corroboration  → NO_ACTION
   drain below threshold AND strong web signal → ELEVATED
   drain above threshold AND low confidence    → RESTRICT
   drain above threshold AND high confidence   → PAUSE
   sources failed beyond tolerance             → cap verdict at RESTRICT
5. ACT      (deterministic)  Ghost → target.pause() on PAUSE only.
6. RECORD   (deterministic)  full Assessment, always, including NO_ACTION.
```

**The model proposes. Deterministic code decides and acts.** The LLM never reaches the pause call — true by construction.

### 5.3 The Equivalence Principle

Validators fetching live web content see different bytes; strict comparison never reaches consensus. Use non-comparative validation: is the leader's verdict *reasonable given the evidence presented*? Include the evidence in the principle; ask about reasonableness, not agreement; keep it short; test adversarially. Document wording and iterations in `docs/equivalence.md`.

### 5.4 Graduated response

| Verdict | Meaning | Action |
|---|---|---|
| `NO_ACTION` | Normal, or unsupported claim | Record only |
| `ELEVATED` | Something is off; insufficient to act | Record, flag |
| `RESTRICT` | Probable exploit, imperfect confidence | Block new deposits |
| `PAUSE` | Confirmed active exploit | Full pause |

### 5.5 The bond

Anyone may call `assess`. Calling requires a bond; on `NO_ACTION` a portion is slashed. Makes spam expensive, the permissionless trigger safe, and gives appeals something to arbitrate. Keep the amount small.

### 5.6 Failure handling — every one a real path with a test

| Failure | Behaviour |
|---|---|
| Web source unreachable | Record as failed, lower confidence, continue. Never substitute. |
| All web sources fail | Judge on on-chain evidence alone; cap at `RESTRICT` |
| LLM call fails | Transaction fails cleanly. No state change. No default verdict. |
| Committee cannot reach consensus | Surface the stall honestly in the UI. |
| Target already paused | `assess` still records; no duplicate action |
| Balance read reverts | Abort. Do not judge without the primary evidence. |

---

## 6. DemoVault

Minimal: `deposit`, `withdraw`, `pause`, `paused`. `pause()` callable only by Circuit — test it. No admin override. Events on every state change. Under 100 lines. Fund it with real testnet value; the drain in the demo is a real transaction.

---

## 7. Frontend

**7.1** A judge opens the URL cold and must understand it within thirty seconds and exercise it themselves.

**7.2 Screens** — Live status (balance, drain rate vs threshold, latest verdict, paused state, all from chain). Assessment history (every assessment incl. `NO_ACTION`, verdict, confidence, measured facts, sources succeeded/failed, reasoning, tx link — `NO_ACTION` entries prominent). Trigger (any visitor runs a live assessment). Evidence detail (exactly what the contract saw; failed sources shown).

**7.3** No "simulate exploit" button; no pre-recorded assessments; no hiding failed sources.

---

## 8. The replay benchmark

10–20 historical cases: real exploits with their public evidence as it existed, and real false alarms. Publish in `bench/`: true positive rate, **false positive rate**, confidence calibration, per-case outcomes. Lead with the worst number. Derive the confidence threshold from the data; state the cost asymmetry; state the sample size.

---

## 9. Demo script

**Beat 1 — the refusal.** Healthy vault, manufactured panic in the evidence → `NO_ACTION`. *A detector that can be triggered by a tweet is a denial-of-service weapon, not a security tool.*
**Beat 2 — the detection.** Real drain from a second wallet → committee → `PAUSE` → vault paused. Show the tx.
**Beat 3 — the receipt.** The assessment record: facts, evidence, failed sources, cited reasoning, committee decision.

---

## 10. Order of work

1. §3.1 verification + hello-world live. 2. Feasibility spikes. 3. DemoVault deployed and funded; pause proven. 4. Circuit contract. 5. Equivalence iteration. 6. Frontend. 7. Replay benchmark; threshold derived. 8. Real drain; full lifecycle. 9. README, verification log, video, submission.

**Cut order:** benchmark size (shrink, never drop) → evidence detail UI → bond → graduated levels. **Never cut:** refusal path, on-chain-evidence-primary, the real drain, honesty of published numbers.

(Superseded by Addendum A §A4.)

---

## 11. Submission checklist

Public repo runnable from a clean clone · live demo URL verified from another machine · name, logo, one-liner (≤180), description (≤1000) · numbered how-to · private verification notes for judges · contract addresses with explorer links · `docs/verification.md` · `docs/equivalence.md` · `bench/` · README limitations · demo video.

## 12. Honest limitations

1. Single demonstration target. 2. Small replay set. 3. Web sources best-effort; the design degrades rather than fails. 4. Latency — slower than a multisig that is awake; faster than one asleep. 5. Not audited.

## 13. Day one

Read docs; deploy hello-world; one real non-deterministic tx; run the consensus spike; start the replay corpus.
