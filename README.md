# Circuit

**Every other circuit breaker reacts after the money starts moving. This one
also reads the proposal that would move it.**

Circuit is an autonomous circuit breaker for DeFi protocols, built as a
GenLayer Intelligent Contract. It has two detection surfaces:

1. **Governance veto** — reads a queued governance proposal, decodes what its
   calldata actually does, compares that with what the description *says* it
   does, and vetoes hostile proposals inside the timelock — before a single
   token moves. *(complete, proven live)*
2. **Drain detection** — measures on-chain outflow against a watched vault,
   weighs external evidence, and pauses on a real attack while refusing to be
   triggered by panic alone. *(complete, proven live)*

Live on GenLayer **Studio Next** (chain 61997). Every claim below links to a
transaction in [`docs/verification.md`](docs/verification.md).

## Why

**Term Labs, August 2026.** Roughly $8.5M lost — not to a drain. Near-zero
voter participation let a single wallet pass a proposal that seized the
protocol's vaults, bypassing the governance delay. No abnormal outflow, no
balance delta, no unusual transfer volume. Threat telemetry saw nothing
because nothing had happened yet. Software integrity was intact because no
code changed. The only way to catch it was to **read the proposal and judge
its intent** — the one thing an AI-consensus contract can do and a
deterministic contract cannot.

**TMXTribe, January 2026.** Drained over ~36 hours while the team watched,
asked for help and shipped patches, but never paused. $1.4M gone, bridged
out. Not a speed problem — a *decision* problem. A 36-hour window is one an
autonomous judge wins comfortably.

Two failure modes; neither is "detect the exploit in progress faster".

## The governance module

A timelock is a delay the protocol *already provides* — hours to days in
production. Committee consensus taking a minute is comfortably fast enough.
This is the one place where AI consensus is not racing a clock but using a
window that already exists.

```
READ     fetch proposal from DemoGovernor (target, calldata, description,
         proposer, tally, quorum, eta)                        deterministic
DECODE   decode calldata against the target's declared        deterministic
         privileged interface → "calls DemoVault.set_owner(0x…dEaD)"
         undecodable bytes aimed at a privileged contract are a signal
CONTEXT  turnout, proposer share and age of holdings,          deterministic
         privileged?, value at risk
JUDGE    is this hostile? does the description match the      LLM, consensus
         calldata? confidence, cited call, reasoning
GATE     table in contracts/circuit.py                         deterministic
ACT      Circuit → DemoGovernor.veto(id) on VETO only          deterministic
RECORD   full assessment stored on-chain, including NO_ACTION  deterministic
```

Every input to the model is read from chain and is byte-identical for every
validator; only the judgment is non-deterministic. Validators re-judge
independently and must agree on `hostile` and `description_matches_calldata`
exactly and on `confidence` within a tolerance; reasoning is stored, never
compared. See [`docs/equivalence.md`](docs/equivalence.md).

### What happened on the live network (2026-09-16)

| proposal | says | does | committee | verdict |
|---|---|---|---|---|
| #0 | "Adjust fee parameter" | `DemoVault.set_owner(0x…dEaD)` | leader gpt-5.4 (99), validators gemini ×2 (100) | **VETO** — child tx vetoed it; `execute()` then reverted on-chain |
| #1 | "Set protocol fee to 0.30% (30 bps)" | `DemoVault.set_fee_bps(30)` | leader gemini (90), gpt-5.4 (96), grok (90), gemini (100) | **NO_ACTION** — privileged, but honest |

Four model families, two proposals, zero disagreements on the decision
fields. Two is a demonstration, not a benchmark — see below.

## The drain module

```
MEASURE  vault balance and withdrawals since the window start → outflow bps   deterministic
GATHER   fetch every evidence source; a failure is recorded, never substituted  non-det
JUDGE    corroboration (STRONG?), exploit probability, cited fact, reasoning    LLM, consensus
GATE     below threshold → NO_ACTION (ELEVATED if strong web signal)            deterministic
         above threshold → RESTRICT (probability < 80) or PAUSE (≥ 80)
         any source failure → no PAUSE; RESTRICT is the safe fallback
ACT      Circuit → DemoVault.restrict() / pause()                                deterministic
RECORD   full receipt, always; NO_ACTION slashes half the caller's bond
```

**A detector that can be triggered by a tweet is a denial-of-service weapon,
not a security tool.** On-chain measurement is primary; text is evidence,
never a trigger. Text alone cannot reach RESTRICT or PAUSE by construction.

### What happened on the live network (2026-09-16)

| beat | measured | evidence | committee | verdict |
|---|---|---|---|---|
| refusal | 0 % outflow, healthy | a live page screaming "DEMOVAULT IS BEING DRAINED" + the DefiLlama hacks feed | leader 4, gpt-5.4 2, claude-sonnet 3 | **NO_ACTION** — bond slashed, nothing touched |
| drain | a second wallet withdrew **50 %** in two real transactions | same sources | leader deepseek 85, claude-sonnet 95, deepseek 95 | **PAUSE** — child tx paused the vault, 119 s after the trigger |

The first live attempt failed consensus for four rounds with every node
saying `NO_ACTION` — on a side field, not the verdict. That failure, why it
happened, and the fix are in [`docs/equivalence.md`](docs/equivalence.md).

### Honest bounding

Some drains are unwinnable at any response speed. Replaying Circuit's
measured trigger-to-pause latency (119 s on Studio Next) against Decurity's
ten reconstructed drain timelines (`bench/replay.py --latency-s 120`, placed
conservatively at the 5-minute mark):

- 7/10 cases still had a majority of at-risk funds on the contract —
  Nomad (8% gone), Euler (4%), Sonne (15%), Curve (16%), Foom, Squid, Rhea.
- 3/10 were already lost — Balancer V2 (93% gone in 5 minutes), CrossCurve
  (78%), Seneca (65%).
- A detector only helps where a pause surface exists; most of those ten
  protocols had none. Circuit's claim is bounded to pausable targets.

Source: Decurity Research, https://rescue-window.decurity.io.

## Contracts

| | |
|---|---|
| `contracts/circuit.py` | the breaker; `assess_proposal` (governance path) |
| `contracts/demo_governor.py` | minimal timelocked governor; `veto()` callable only by the bound Circuit address; `execute()` reverts when vetoed |
| `contracts/demo_vault.py` | the protected protocol; governor is `owner` (params, ownership, sweep), Circuit is `controller` (pause) |

Current hardened set (deployed and exercised 2026-09-17): vault `0xbbad9F3bFC25694c250F3334c7fa3c310f7cF90E` ·
governor `0x867D7F43484efDfaE55e79e9A37D8C8546e7cf24` ·
Circuit `0x23C06AD5844112915a261013AdE273e1207f9047`.
It contains fresh governance veto and drain pause receipts; prior live sets remain
available through the UI deployment selector. Explorer: https://explorer-studio-dev.genlayer.com.

The demo governor's windows are 180 s voting / 300 s timelock so a demo fits
in minutes. Production windows are hours to days, which only widens Circuit's
margin.

## Run it

```
export PATH=$HOME/.nvm/versions/node/v24.21.0/bin:$PATH
npm test                                  # 41 direct-mode contract tests
npm run serve:web                         # governance watch UI on :8080
node scripts/read.cjs  <addr> get_proposals
node scripts/write.cjs <circuit> post_bond '[]' 20000000000000000
node scripts/write.cjs <circuit> assess '["demovault"]'
node scripts/write.cjs <circuit> assess_proposal '[0]'
python3 bench/replay.py --latency-s 120
```

Network scripts use `genlayer-js 2.0.0-rc.1` directly (the CLI cannot submit
fee-bearing transactions to Studio Next). Studio-specific quirks — v0.3
GenVM API, simulation clock lag on time-gated calls, message fee
allocations — are documented in `docs/verification.md` and `PROGRESS.md`.

## Not simulated

No mock proposals, no mock verdicts, no mock vetoes. Every row in the UI is a
`readContract` against the live contracts; every verdict is the stored
output of a real validator committee; every veto is a real child
transaction. Where something is not yet proven, the docs say so.
