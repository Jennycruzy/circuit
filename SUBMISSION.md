# Circuit — live proof handoff

**One-line pitch:** Circuit is a GenLayer safety layer that reads governance
intent before execution and measures vault outflow before it decides to pause.

## Start here

**Live UI:** [Open the published Circuit UI](https://circuit-lemon-five.vercel.app/).
**Operator console:** [Open the wallet-gated operator console](https://circuit-lemon-five.vercel.app/operator.html).

In 30 seconds:

1. Select **Current live set**.
2. Verify the vault reads `paused=true`, `restricted=true`, balance `0.025 GEN`.
3. Open drain **#1**: 50% measured outflow → `PAUSE` → finalized child receipt.
4. Open proposal **#0**: “Adjust fee parameter” actually calls
   `set_owner(0x…dEaD)` → `VETOED` → finalized child veto receipt.
5. Open the receipt links to see the exact Studio Next parent and child hashes.

No wallet is needed. The UI reads the public RPC directly and keeps the raw
assessment/evidence fields visible.

## What is proven live

- Fresh Studio Next set (chain 61997):
  - Vault `0xbbad9F3bFC25694c250F3334c7fa3c310f7cF90E`
  - Governor `0x867D7F43484efDfaE55e79e9A37D8C8546e7cf24`
  - Circuit `0x23C06AD5844112915a261013AdE273e1207f9047`
- Governance: hostile proposal assessed `VETO`; Governor reads `VETOED`; [parent assessment](https://explorer-studio-dev.genlayer.com/tx/0x4aa5b9e70832db4a8cc7488a7e2d1e95eb1db09f3fba7ce36fefa39741e06907) → [child veto](https://explorer-studio-dev.genlayer.com/tx/0x80a844a39565e7305924bb4d6e004f2016620ea99468d6a7cc44a9db7773890a).
- Drain refusal: zero outflow assessed `NO_ACTION`; [parent assessment](https://explorer-studio-dev.genlayer.com/tx/0x07cf801f7a716cbbd942a5dbf700f2c16d17a1fa8d8a3a377e77f83375ba3efd); no child action emitted.
- Drain response: controlled 50% withdrawal assessed `PAUSE`; Vault reads paused
  and restricted; [parent assessment](https://explorer-studio-dev.genlayer.com/tx/0x79d21891660620e9d084098de06cf1668b73d3d9f665f817350eb09875293e70) → [child pause](https://explorer-studio-dev.genlayer.com/tx/0x53489162f20828a8fc332826835b069a35237f2dbeec43858793dbcf5bf51c4a).
- Full parent/child and deployment receipts: [`docs/verification.md`](docs/verification.md).

## Why the design matters

Governance attacks can seize a vault without abnormal outflow. Drain alarms can
be denial-of-service weapons if text alone can trigger them. Circuit keeps the
safety boundary deterministic: on-chain measurements decide the drain gate;
committee judgment interprets bounded evidence; the contract records every
outcome, including `NO_ACTION`.

## Honest limits

Studio Next is the demonstrated network. Circuit is bounded to targets exposing
a readable state and a pause/restrict surface. Partial or total evidence-source
failure cannot produce `PAUSE`; opaque governance targets become `FLAG`. The
larger corpus separates six offline fixtures from the three measured live cases;
fixtures are not reported as live benchmark results.

## Reproduce

```bash
npm test
npm run build:web
python3 bench/replay.py --latency-s 120
python3 bench/governance_score.py
```

Release includes the receipt-index, proof-path, corpus, and submission polish changes. The final release commit is recorded in the repository log.
