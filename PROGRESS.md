# PROGRESS

## Done
- 2026-09-16: Read GenLayer skills repo + live docs. Answers in `docs/verification.md`.
- 2026-09-16: Tooling installed: genlayer CLI 0.39.2, genvm-linter 0.11.0,
  genlayer-test 0.29.2, genlayer-py 0.16.3 (venv `~/.venv-circuit`), Node 24 via nvm.

- 2026-09-16: Hello-world deployed to studionet; first real nondet tx (web
  fetch + LLM) reached `MAJORITY_AGREE` —
  `0xb3fc3ea5c5f17a2bb6bf278a56d8ef75c466d07dde125cb57e461d4579f2543a`.
  Open-ended LLM text failed consensus across 4 rounds first; closed enum
  passed in 1 round. Details in `docs/verification.md`.

- 2026-09-16: **Target network is Studio Next (61997)** per organisers. Hello-world
  redeployed there on GenVM v0.3.0: contract
  `0xA8E321f40c5230f9356e08F77420fF7FB06aE1D1`, nondet tx
  `0xdd623724…4765` MAJORITY_AGREE. Deploy/write/read scripts on
  genlayer-js 2.0.0-rc.1 in `scripts/`.

- 2026-09-16 19:31: **Spike 3 (Studio form) PROVEN.** `emit_pause` parent
  `0x3299…25f8` → child `0x2421…870c` (`triggered_on: finalized`) paused
  DemoVault `0x9Be50f5A…91CF`; ~32 s parent→child. Evidence in verification log.
- 2026-09-16 20:05: **Addendum §A2.7 blockers all resolved live** with
  `spikes/gov_probe.py` (`0xf4c67DA5…1c21`): in-VM calldata decode
  (`gl.calldata`), cross-contract reads (`get_at().view()`), list/dict/bytes
  return shapes, and two message targets in one tx. See verification log.

- 2026-09-16 20:06: **DemoGovernor live; veto path PROVEN (A4 step 5).**
  Governor `0x16C1958C…fA6e`, vault `0x9804c962…B570` (owner = governor).
  Hostile proposal 0 (`set_owner(0x…dEaD)` described as "Adjust fee
  parameter") vetoed by a contract message (child `0x405b5039…88ad`);
  `execute(0)` reverted on-chain with `proposal was vetoed`. 18 direct tests.

- 2026-09-16 20:45: **Governance path complete end to end on Studio Next
  with a real committee.** Circuit `0x7Fc47843…a984` vetoed hostile proposal
  0 (VETO, leader gpt-5.4 99, validators gemini 100) and cleared benign
  proposal 1 (NO_ACTION, 4 model families agree). `execute(0)` reverted
  on-chain. Benign proposal on the earlier governor executed for real
  (`fee_bps` 0 → 30). 27 direct tests.

## Current status (2026-09-16 20:45 UTC)
- Live demo set: vault `0x93A35A1a192E2A67e0816d178D8b14ed96590977`,
  governor `0xad2dd2445ff40Cbcc23D04A539C3c527Af0C5574`, Circuit
  `0x7Fc4784365a6c209753ae35740a89e03bd45a984`. Circuit is also the vault's
  `controller` (pause authority) — the drain path can bind to this set.
- §A4 steps 1–5 and 7 done. Step 6 (`assess`, drain path, main-spec §5.2)
  needs the main spec text in-session; not started. Steps 8–12 not started.

## Superseded status (2026-09-16 20:06 UTC)
- Addendum A received. Order of work now follows §A4. Steps 1–5 of §A4 are
  done except DemoGovernor itself (next). The governance path has no web
  inputs, so it does not depend on spike 2; if spike 2 fails it is the primary
  path (§A2.6).
- **Design decision (Studio):** DemoGovernor is an Intelligent Contract whose
  proposals carry `target` + raw GenVM calldata bytes + description. Circuit
  decodes the bytes with `gl.calldata.decode`, checks the method against the
  target's registered privileged interface, and compares it with the stated
  description. Veto and pause both go out as `emit(on="finalized")` messages.

- `contracts/demo_vault.py` is deployed on Studio Next at
  `0xa0d10d68050f1f3f993ca99D3E150F95371886eB` (tx
  `0x3e47c0835891728daac2ad11bf438dfaf4c3045cb77a88ebff0ff6fc60eacfb1`).
  Its initial live state was unpaused, unconfigured, and zero balance.
- `spikes/ic_pause.py` is deployed at
  `0xEe750F2EEF9EDBC10551fF741a05a74C1A1173DB` (tx
  `0x36626ac9327c64ffe48892a48a1c7a7cd9233c2c7e06c0daa880990ee9a10ecb`).
  The vault accepted the one-time controller binding in
  `0x34eb04162d06e4699ac0d6230a5382b27037e6ce34f449e7cb51e0df9900e57d`.
- `emit_pause` was simulated but not submitted. Studio returned an execution
  error whose leader stderr reported that `genlayer` has no attribute
  `get_contract_at`. No pause state change occurred. The source now uses the
  runtime's `gl.contract.get_at`; a fresh vault/probe pair is needed because
  the controller binding is one-time.
- The earlier EVM probe at
  `0x2c4A31e7948D1E33D46c0Cc97693b8ef13720c3f` remains unresolved, and its
  recorded target is not deployed. Studio EVM/Ghost support is not claimed.
- Tooling: `export PATH=$HOME/.nvm/versions/node/v24.21.0/bin:$PATH`; all
  network ops use `scripts/{deploy,write,read}.cjs` with genlayer-js
  2.0.0-rc.1. The CLI is not used for Studio Next transactions.
- Contracts use the v0.3.0 header/API (see verification log).

## Next
- Circuit `assess` (drain path) per main-spec §5.2 — paste the main spec.
- `docs/equivalence.md` (both paths); governance-side observations already in
  the verification log.
- Frontend (§A5): governance watch + side-by-side + proposal detail; reads via
  genlayer-js `readContract` on the three live addresses.
- Replay benchmark (§A3): Decurity rescue-window cases + governance corpus;
  false-veto rate.
- Second wallet for the demo's hostile proposer (currently the deployer).
- README with TMXTribe / Term Labs framing; demo video.
- Full consensus spike: live changing page + enum verdict + confidence
  tolerance, run ≥10 times; record agree/disagree rate.
- Ghost→pause() spike — Bradbury only.
- Start the replay corpus (`bench/`).

## Blocked
- Studio does not implement calls to EVM contracts. The Solidity/Ghost path is
  replaced by the proven IC-to-IC message path; a Bradbury port would swap the
  proxy type only.
- The Circuit contract, DemoGovernor, frontend, and replay benchmark have not
  been created yet.

## Findings that shape the design
- Committees are heterogeneous (gpt-5.4, gemini, gemma, qwen, mistral, sonnet,
  kimi, gpt-oss seen in one afternoon). Validators must compare closed enums /
  bounded numbers only; free text is stored, never compared.
- `genlayer trace` does not work on studionet; read
  `eth_getTransactionByHash → consensus_history` directly.

- Studio Next runs GenVM v0.3.0; the `genlayer-dev` skill and most docs describe
  v0.2. Header, imports, `run_nondet_default`, no `u256()` — see verification log.
- GenLayer CLI 0.40.0-rc.3 cannot submit fee-bearing txs to Studio Next;
  genlayer-js 2.0.0-rc.1 can. All network operations go through `scripts/`.

## Doc divergences from SPEC.md
0. **Network.** Spec assumes Bradbury (real GEN, EVM interop). Hackathon requires
   Studio Next (61997), where EVM interop is documented as not implemented.
   §6's Solidity/Ghost target is replaced here by an Intelligent-Contract vault
   and IC-to-IC message path. The live pause action is not yet proven.
1. **§5.3 non-comparative EP → comparative re-derivation.** Docs: non-comparative
   is for open-ended outputs (summaries); for classification/safety/settlement
   decisions the validator must independently re-derive and compare the decision
   field. Validators should independently re-derive and compare bounded decision
   fields; free-form reasoning should not be compared. Circuit is not implemented
   yet, so this remains a design requirement rather than an executed result.
2. **§5.2 step 5 ACT is not instantaneous.** IC messages are emitted only on
   `finalized`. The pause lands after the appeal window closes. Latency is to be
   measured and stated honestly in README.
3. **§3.3 spike 3 cannot run on Studio in its EVM form.** Run in IC-to-IC form
   instead and proven 2026-09-16 19:31 (see verification log).
4. **§3.2 "Skills plugin one-command path".** The plugin is skill docs wrapping
   the CLI, not a deploy tool. CLI is the path.
5. **Cross-contract reference API.** The current public messages page shows
   `gl.get_contract_at`, but the deployed v0.3.0 runtime has no such attribute.
   A real simulation failed with that exact runtime error. The source now uses
   `gl.contract.get_at`; re-run live and proven.
6. **Addendum §A2.3 "Solidity governor".** Written as an Intelligent Contract on
   Studio; proposal calldata is GenVM calldata, not EVM ABI. The description-vs-
   calldata mismatch signal is unchanged.
7. **§A2.4 GATE table.** The table does not separate the hostile verdict from
   the confidence in it, which would make every honest privileged proposal at
   least FLAG (contradicting demo beat 2's NO_ACTION). Implemented: confidence
   = confidence in `hostile`; non-hostile + matching description → NO_ACTION;
   non-hostile + mismatch → FLAG; the rest of the table as written.
8. **Studio simulation clock.** Fee estimation simulates at the last state
   snapshot's datetime, so time-gated calls fail estimation; `scripts/write.cjs
   --force` / `--messages` submit them anyway (see verification log).

## Audit review — 2026-09-16 14:35 UTC
- The Studio account was funded with `sim_fundAccount`; no Bradbury GEN was
  required for the deployed Studio work. The hello deployment and its
  web-fetch/LLM transaction are live evidence.
- `node scripts/read.cjs` reads the hello state as
  `last_status: 200`, `last_body_len: 559`, and `runs: 1`. The probe state
  is still empty.
- Public RPC checks returned no EVM bytecode for the hello contract, probe, or
  recorded target. The target's GenLayer code and schema lookup returned
  `Contract ... not found`; the target is not deployed.
- `pytest tests/direct/test_demo_vault.py -q` passes all 6 direct-runtime
  tests. `npm test` still exits with the package's placeholder `no test
  specified` failure.
- The hello source does not pass the installed linter's reachability check, and
  both hello and probe validation cannot load the pinned v0.3 runner archive.
  The probe's three static checks pass, but that is not full validation.
- The current package versions are `genlayer-js 2.0.0-rc.1`,
  `genlayer-py 0.19.0rc2`, and `genlayer-test 0.30.0rc2`; the earlier
  tooling notes list older Python and test versions.
- `scripts/write.cjs` uses `estimateTransactionFeesForWrite` and waits for
  finalization. Its first child-message simulation reached contract execution
  and failed on the stale API name above; no transaction was submitted.
