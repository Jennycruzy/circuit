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

## Current status (2026-09-16 12:32 UTC)
- `spikes/evm_probe.py` is deployed on Studio Next at
  `0x2c4A31e7948D1E33D46c0Cc97693b8ef13720c3f` (tx `0xa022162b…14f3`).
- The recorded target `0xb7278A61aa25c888815aFC32Ad3cC52fF24fE575` has no EVM
  bytecode and is not an Intelligent Contract. The probe cannot establish EVM
  support without a real deployed target.
- A real `view_paused` call was submitted as
  `0xfc423a5653ae69efaaf6444a3a31535958b2fab2655acc60619cbcfe9681f27b`.
  At the last check it remained `PROPOSING` with no consensus receipt; the
  helper also received an HTML response where JSON-RPC was expected. This is
  unresolved and is not recorded as a success or failure.
- Tooling: `export PATH=$HOME/.nvm/versions/node/v24.21.0/bin:$PATH`; all
  network ops via `scripts/{deploy,write,read}.cjs` (genlayer-js 2.0.0-rc.1).
  Do not use the CLI for Studio Next transactions.
- Contracts must use the v0.3.0 header/API (see verification log).

## Next
- Deploy a real Studio-compatible vault and verify IC-to-IC control with a
  live transaction before claiming a pause path.
- Full consensus spike: live changing page + enum verdict + confidence
  tolerance, run ≥10 times; record agree/disagree rate.
- Ghost→pause() spike — Bradbury only.
- Start the replay corpus (`bench/`).

## Blocked
- The recorded EVM target is absent, and Studio does not implement calls to
  EVM contracts beyond value transfers. The Solidity/Ghost path cannot be
  claimed from the current deployment.
- The Circuit contract, vault contract, frontend, replay benchmark, and tests
  have not been created yet.

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
   §6 (Solidity DemoVault + Ghost pause) may need to change to an
   Intelligent-Contract vault paused by IC-to-IC message. This is not confirmed
   by the unresolved probe transaction.
1. **§5.3 non-comparative EP → comparative re-derivation.** Docs: non-comparative
   is for open-ended outputs (summaries); for classification/safety/settlement
   decisions the validator must independently re-derive and compare the decision
   field. Circuit uses `run_nondet_unsafe` + re-run + compare `verdict` exactly,
   `confidence` within tolerance. The "reasonableness question" from the spec is
   kept as the *prompt criteria*, not as the validation mechanism.
2. **§5.2 step 5 ACT is not instantaneous.** IC→EVM external messages are emitted
   only on `finalized`. The pause lands after the appeal window closes. Latency
   to be measured and stated honestly in README.
3. **§3.3 spike 3 cannot run on Studio.** EVM contract calls are unimplemented in
   Studio; Bradbury only.
4. **§3.2 "Skills plugin one-command path".** The plugin is skill docs wrapping
   the CLI, not a deploy tool. CLI is the path.

## Audit review — 2026-09-16 12:32 UTC
- The Studio account was funded with `sim_fundAccount`; no Bradbury GEN was
  required for the deployed Studio work. The hello deployment and its
  web-fetch/LLM transaction are live evidence.
- `node scripts/read.cjs` reads the hello state as
  `last_status: 200`, `last_body_len: 559`, and `runs: 1`. The probe state
  is still empty.
- Public RPC checks returned no EVM bytecode for the hello contract, probe, or
  recorded target. The target's GenLayer code and schema lookup returned
  `Contract ... not found`; the target is not deployed.
- `npm test` currently exits with the package's placeholder
  `no test specified` failure. No application tests exist.
- The hello source does not pass the installed linter's reachability check, and
  both hello and probe validation cannot load the pinned v0.3 runner archive.
  The probe's three static checks pass, but that is not full validation.
- The current package versions are `genlayer-js 2.0.0-rc.1`,
  `genlayer-py 0.19.0rc2`, and `genlayer-test 0.30.0rc2`; the earlier
  tooling notes list older Python and test versions.
- `scripts/write.cjs` waits for a decided receipt and uses the generic fee
  estimator without an explicit message allocation. The current fee and
