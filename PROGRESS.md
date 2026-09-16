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

## Handoff (2026-09-16 11:45 UTC — session stopped by user, credits low)
- `spikes/evm_probe.py` is deployed on Studio Next at
  `0x2c4A31e7948D1E33D46c0Cc97693b8ef13720c3f` (tx `0xa022162b…14f3`) but its
  two methods have NOT been called yet. Resume with:
  `node scripts/write.cjs 0x2c4A31e7948D1E33D46c0Cc97693b8ef13720c3f view_paused '["0xb7278A61aa25c888815aFC32Ad3cC52fF24fE575"]'`
  and the same with `emit_pause`. Record the result in docs/verification.md
  under "Open: IC→EVM on Studio Next". Expected: not implemented → DemoVault
  becomes an Intelligent Contract paused via `gl.contract.get_at(v).emit(on='finalized').pause()`.
- Tooling: `export PATH=$HOME/.nvm/versions/node/v24.21.0/bin:$PATH`; all
  network ops via `scripts/{deploy,write,read}.cjs` (genlayer-js 2.0.0-rc.1).
  Do not use the CLI for Studio Next transactions.
- Contracts must use the v0.3.0 header/API (see verification log).

## Next
- Finish spike 3 (above) → decide DemoVault-as-IC + IC→IC pause.
- Full consensus spike: live changing page + enum verdict + confidence
  tolerance, run ≥10 times; record agree/disagree rate.
- Ghost→pause() spike — Bradbury only.
- Start the replay corpus (`bench/`).

## Blocked
- Nothing external. (Bradbury faucet no longer needed — Studio Next is the target.)

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
   §6 (Solidity DemoVault + Ghost pause) is therefore expected to change to an
   Intelligent-Contract vault paused by IC→IC message. Confirmed by spike 3 next.
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
