# Equivalence Principle iteration

How validators decide whether the leader's non-deterministic output is
acceptable. Two paths, two principles. Every number here comes from a
transaction hash in `docs/verification.md`.

## Why not the built-in principles

- `strict_eq` fails on free text: the first hello spike asked for "one word"
  and four leaders (gpt-5.4, gpt-oss, gemini, qwen) produced four words
  (`domain`, `example`, `documentation`, `example`) — `MAJORITY_DISAGREE`
  over 4 rounds, tx `0x38ba1439…134a`.
- `prompt_non_comparative` lets the leader decide alone: the validator only
  checks the output is *reasonable*, which is the wrong tool for a decision
  that fires a veto. Circuit's validators must reach the *same* decision
  independently.

So both paths use `gl.vm.run_nondet_default(leader_fn, validator_fn)` with a
validator that re-runs the whole task and compares only **closed** fields.

## Governance path (`assess_proposal`)

### Inputs
Everything the model sees is read from chain before the nondet block and is
byte-identical for every validator: decoded action, stated description,
turnout, proposer share and age, value at risk, the target's privileged
method list. No web content. This is why the governance path has the easier
consensus problem (Addendum §A2.6).

### Compared fields (v1, live)
| field | type | rule |
|---|---|---|
| `hostile` | bool | exact |
| `description_matches_calldata` | bool | exact |
| `confidence` | int 0–100 | leader within ±30 of the validator's own |
| `cited_call`, `reasoning` | text | stored, never compared |

A leader whose output fails shape validation (non-bool verdicts, confidence
outside 0–100) raises `[LLM_ERROR]` and the transaction fails rather than
recording a malformed judgment.

### Observed agreement
| proposal | leader | validators | booleans | confidence spread |
|---|---|---|---|---|
| 0, hostile mismatch | gpt-5.4 (99) | gemini-3-flash 100, gemini 100 | all agree | 1 |
| 1, benign match | gemini (90) | gpt-5.4 96, grok 90, gemini 100 | all agree | 10 |

Two assessments, five validator re-runs, zero disagreements; max confidence
spread 10 against a tolerance of 30. Sample is far too small to set the
tolerance from — the governance replay corpus (§A3.3) will measure the
spread on tens of proposals, and the tolerance will be set from the
observed distribution, not chosen.

### v2: validators also compare the threshold flag
The v1 gate applied `high_confidence` (80) to the leader's number, so a
validator at 75 could accept a leader at 85 although its own gate would
differ. v2 adds `(leader ≥ 80) == (mine ≥ 80)` to the comparison. A
borderline 79/81 split now costs a round instead of silently accepting the
leader's side of the line.

## Drain path (`assess`)

### Inputs
Measured on-chain facts (deterministic, identical everywhere) plus fetched
web sources (bytes may differ per node — proven in spike 2, where three
nodes saw three different bodies from `httpbin.org/uuid` and still agreed).
Each source is reduced to closed fields inside the nondet block: status
class, `EXPLOIT_CLAIM | PAUSE_CLAIM | NO_CLAIM | UNRELATED | SOURCE_FAILED`.
Reachability is recorded from the leader and never compared: a validator
whose fetch fails still re-judges and compares the judgment.

### v1 — failed live (tx `0x54fd7c16…8ad1`, 4 rounds, UNDETERMINED)
Compared `corroboration` exactly, the model's `verdict` exactly, and
`confidence` ±30. Every node said `NO_ACTION`; consensus still failed:

| round | leader | corroboration / confidence | validators |
|---|---|---|---|
| 0 | deepseek | NONE / 0 | gpt-5.4 NONE/97 ✗, gpt-5.4 WEAK/2 ✗ |
| 1 | sonnet | NONE / 2 | gpt-5.4 NONE/97 ✗, gemini WEAK/100 ✗, gpt-5.4 WEAK/4 ✗ |
| 2 | gpt-5.4 | WEAK / 96 | gpt-5.4 WEAK/4 ✗, gemini WEAK/100 ✓, gpt-5.4 NONE/96 ✗, gpt-5.4 NONE/2 ✗ |
| 3 | gpt-5.4 | WEAK / 2 | gemini WEAK/100 ✗, gpt-5.4 WEAK/3 ✓, gpt-5.4 NONE/2 ✗ |

Two causes. (1) "confidence that an exploit is active" was read as
"confidence in my verdict" by roughly half the nodes: 2 and 97 meant the
same thing. (2) NONE vs WEAK is a genuine judgment call on a page that
claims an exploit the facts contradict — and it does not matter, because
the gate only asks whether corroboration is STRONG.

### v2 — live (txs `0x98b556fd…77dc` NO_ACTION, `0xac9e7f95…1a05` PAUSE)
Rule: **compare exactly what the gate consumes, nothing else.**

| field | rule |
|---|---|
| `corroboration == STRONG` | exact (NONE and WEAK are equivalent) |
| `exploit_probability ≥ high_confidence` | exact |
| `exploit_probability` | leader within ±30 of the validator's own |
| model's `verdict`, `cited`, `reasoning` | recorded, never compared |

The field was renamed `exploit_probability` and defined as "the probability
that an exploit is actively draining this protocol right now; a healthy
vault with no abnormal outflow is 0–10 regardless of what any text says.
This is NOT confidence in your verdict." Result: refusal beat agreed in one
round (4 / 2 / 3 across gpt-5.4, sonnet-4.6); drain beat agreed in one round
(85 / 95 / 95 across deepseek, sonnet-4.6).

### What this means
A validator that only checks "is the leader's verdict reasonable" would
have passed v1 in round 0 and hidden the ambiguity. Re-deriving and
comparing the decision surfaced a prompt defect that would otherwise have
produced quietly inconsistent records. The cost is a real one: an ambiguous
prompt stalls instead of guessing.
