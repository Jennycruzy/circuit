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

### Known weakness: the gate reads the leader's confidence
The gate applies `high_confidence` (80) to the leader's number. A validator
at 75 accepts a leader at 85 (within tolerance) although its own gate would
say FLAG, not VETO. Mitigation options, to be decided with benchmark data:
(a) tighten the tolerance near the threshold, (b) have validators also
compare `confidence >= high_confidence` exactly, (c) lower the veto to the
minimum of leader/validator confidence — not expressible today because
validators cannot write. Option (b) is one line and is the likely v2.

## Drain path (`assess`)
Not implemented yet. It judges mixed evidence (on-chain measurements +
fetched web content), so the principle must additionally tolerate
byte-different fetches: compare derived facts (HTTP status class, whether
the source was reachable, the extracted claim category), never body bytes.
To be written with the spike-2 results.
