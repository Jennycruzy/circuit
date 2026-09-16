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

## Next
- Repeat hello-world on Bradbury once funded.
- Full consensus spike: live changing page + enum verdict + confidence
  tolerance, run ≥10 times; record agree/disagree rate.
- Ghost→pause() spike — Bradbury only.
- Start the replay corpus (`bench/`).

## Blocked
- **Bradbury funding.** Faucet is Turnstile-gated; a human must claim 100 GEN at
  https://testnet-faucet.genlayer.foundation/ for deployer `0xbdeb496b84d74806d631a51141144ef3a3d4a146`. Everything EVM-related (DemoVault, pause) is
  Bradbury-only, so this gates §3.3 spike 3 and §6.

## Findings that shape the design
- Committees are heterogeneous (gpt-5.4, gemini, gemma, qwen, mistral, sonnet,
  kimi, gpt-oss seen in one afternoon). Validators must compare closed enums /
  bounded numbers only; free text is stored, never compared.
- `genlayer trace` does not work on studionet; read
  `eth_getTransactionByHash → consensus_history` directly.

## Doc divergences from SPEC.md
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
