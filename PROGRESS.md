# PROGRESS

## Done
- 2026-09-16: Read GenLayer skills repo + live docs. Answers in `docs/verification.md`.
- 2026-09-16: Tooling installed: genlayer CLI 0.39.2, genvm-linter 0.11.0,
  genlayer-test 0.29.2, genlayer-py 0.16.3 (venv `~/.venv-circuit`), Node 24 via nvm.

## Next
- Deploy hello-world to studionet (gasless) AND Bradbury (needs faucet).
- One real nondet tx (web fetch + LLM) — record hash.
- Consensus spike with the re-run-and-compare-verdict validator.
- Ghost→pause() spike — Bradbury only.
- Start the replay corpus (`bench/`).

## Blocked
- **Bradbury funding.** Faucet is Turnstile-gated; a human must claim 100 GEN at
  https://testnet-faucet.genlayer.foundation/ for deployer `0xbdeb496b84d74806d631a51141144ef3a3d4a146`. Everything EVM-related (DemoVault, pause) is
  Bradbury-only, so this gates §3.3 spike 3 and §6.

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
