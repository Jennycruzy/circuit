# Verification Log

Every technical claim in `SPEC.md` checked against the live GenLayer docs and
the live network before implementation. Timestamps are UTC. Entries are
append-only; nothing here is edited after the fact.

Sources read (2026-09-16):
- https://github.com/genlayerlabs/skills — `genlayer-dev` plugin v1.1.4 skills
  (`write-contract`, `genlayer-cli`, `genvm-lint`, `direct-tests`, `integration-tests`)
- https://docs.genlayer.com/developers/intelligent-contracts/features/interacting-with-evm-contracts
- https://docs.genlayer.com/developers/intelligent-contracts/features/messages
- https://docs.genlayer.com/developers/intelligent-contracts/features/web-access
- https://docs.genlayer.com/developers/intelligent-contracts/features/non-determinism
- https://docs.genlayer.com/developers/intelligent-contracts/features/calling-llms
- https://docs.genlayer.com/developers/intelligent-contracts/equivalence-principle
- https://docs.genlayer.com/developers/networks
- https://docs.genlayer.com/developers/decentralized-applications/reading-data
- https://docs.genlayer.com/FAQ

## 3.1 Documentation verification

### Q1. How are non-deterministic blocks written? — 2026-09-16 09:40 UTC

All `gl.nondet.*` calls must be inside a function passed to a nondet runner;
they fail in plain contract code. Storage writes, `gl.get_contract_at()`, and
`.emit()` must be OUTSIDE nondet blocks (linter enforces this).

```python
def leader_fn():
    res = gl.nondet.web.get(url)                       # or gl.nondet.web.request(url, method='GET')
    body = res.body.decode("utf-8")
    out = gl.nondet.exec_prompt(prompt, response_format="json")   # returns dict
    return out
def validator_fn(leader_result: gl.vm.Result) -> bool:
    if not isinstance(leader_result, gl.vm.Return): return False
    mine = leader_fn()
    return mine["verdict"] == leader_result.calldata["verdict"]
result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
```

Contracts must begin with a pinned runner header:
`# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }`
(`py-genlayer:test` / `:latest` are rejected by all networks.)

Status: CONFIRMED from docs and the installed skill. Not yet executed on-network (see §3.2).

### Q2. Equivalence Principle modes; exact API for non-comparative — 2026-09-16 09:45 UTC

Modes: `gl.eq_principle.strict_eq(fn)`, `gl.eq_principle.prompt_comparative(fn, principle=)`,
`gl.eq_principle.prompt_non_comparative(fn, task=, criteria=)`, and custom
`gl.vm.run_nondet_unsafe(leader_fn, validator_fn)` (recommended) /
`gl.vm.run_nondet(...)`.

**DIVERGENCE FROM SPEC §5.3.** The docs and the `write-contract` skill explicitly
say non-comparative validation is the wrong tool for "classification, scoring,
... safety, ... settlement decisions": "If the validator only checks that the
leader chose an allowed label ... the leader is deciding alone." The recommended
pattern is a custom validator that independently re-runs the task and compares
the decision field(s) with tolerance. Circuit will therefore use
`run_nondet_unsafe` with a validator that re-measures, re-fetches, re-judges,
and compares the **verdict tier** (exact) and **confidence** (tolerance, with a
gate at tier boundaries). Recorded in PROGRESS.md. The consensus spike (§3.3)
tests this pattern.

### Q3. Web access constraints — 2026-09-16 09:45 UTC

API: `gl.nondet.web.get(url)`, `gl.nondet.web.request(url, method=, body=)`,
`gl.nondet.web.render(url, mode='html'|'text'|'screenshot')`. Response exposes
`.status` / `.status_code` (docs show both spellings — verify in SDK) and `.body` (bytes).
Docs state no explicit timeout, size limit, or scheme whitelist on the page.
Leader and validators fetch independently — bytes may differ. Guidance:
extract stable fields or derive a status before comparing.
Status: CONFIRMED API shape; limits UNKNOWN — will be measured in spike 1.

### Q4. Can an IC call a Solidity contract on GenLayer Chain? — 2026-09-16 09:45 UTC

YES, documented. Mechanism:

```python
@gl.evm.contract_interface
class IPausable:
    class View:
        def paused(self) -> bool: ...
    class Write:
        def pause(self) -> None: ...
IPausable(target).view().paused()      # sync read
IPausable(target).emit().pause()       # external message via ghost, on='finalized' ONLY
```

Executed by the IC's ghost contract via `handleOp()`; the EVM `msg.sender` is
the ghost address == IC address. Type mapping: u256→uint256, Address→address,
bool→bool, str→string, bytes→bytes.

Constraints that change the plan:
- **External messages fire only on finality** (after the appeal window). The
  pause is not instantaneous on acceptance. Latency = time-to-finality on
  Bradbury — to be measured.
- **Studio (studionet / localnet) does NOT implement `@gl.evm.contract_interface`
  calls.** "EVM contract interaction beyond value transfers to EOAs is not
  implemented." The Ghost→pause() spike can only be run on Testnet Bradbury.
- Whether method names are auto-mapped snake_case→camelCase is not stated.
  Will verify with the spike (use single-word `pause`/`paused` to avoid the question).

### Q5. Deployment path — 2026-09-16 09:45 UTC

CLI (`npm i -g genlayer`; `genlayer network set testnet-bradbury`;
`genlayer deploy --contract ...`). The Skills plugin (`genlayerlabs/skills`)
is a set of Claude Code skill docs + a docs MCP; it wraps the same CLI.
Studio web UI also deploys, but not needed.

Bradbury needs GEN: faucet https://testnet-faucet.genlayer.foundation/ —
Cloudflare Turnstile, **must be claimed manually by a human**, 100 GEN / 24h.

### Q6. Gas / cost limits on fetches and LLM calls — 2026-09-16 09:45 UTC

Not stated on the pages read. Studionet has per-IP rate limits (60/min,
1000/hr, 10000/day) and a 32 in-flight tx cap per sender. Docs mention a
"Fees & Transaction Policy" page for Bradbury — to be read before the spikes.
Status: UNKNOWN — measure empirically.

### Q7. Reading contract state from a frontend — 2026-09-16 09:45 UTC

`genlayer-js`: `createClient({ chain })` then
`client.readContract({ address, functionName, args, transactionHashVariant: TransactionHashVariant.LATEST_FINAL })`.
Chains exported from `genlayer-js/chains`. Writes via `client.writeContract` +
`client.waitForFinalization({ hash })`.

### Network facts — 2026-09-16 09:45 UTC

| | Bradbury | Studionet |
|---|---|---|
| GenLayer RPC | https://rpc-bradbury.genlayer.com | https://studio.genlayer.com/api |
| Chain RPC (EVM) | https://rpc.testnet-chain.genlayer.com | — |
| Chain ID | 4221 | 61999 |
| Explorer | explorer-bradbury.genlayer.com | explorer-studio.genlayer.com |
| EVM explorer | explorer.testnet-chain.genlayer.com | — |
| Gas | real GEN, faucet | gasless |
| EVM interop | yes | **no** |

## 3.2 Environment verification

### Tooling — 2026-09-16 11:10 UTC

- genlayer CLI 0.39.2 (npm, Node 24.21.0 via nvm). A first install was
  interrupted mid node-gyp build and left a dangling symlink; reinstalled.
- genvm-linter 0.11.0, genlayer-test 0.29.2, genlayer-py 0.16.3, web3 8.0.0
  in venv `~/.venv-circuit`.
- Claude Code plugins `genlayer-dev` 1.1.4 and `genlayer-docs` 1.1.0 installed.

(further entries appended as each check is executed)

### Deployer account — 2026-09-16 11:15 UTC

- `genlayer account create --name circuit-deployer` → keystore
  `~/.genlayer/keystores/circuit-deployer.json` (password in
  `~/.circuit-keystore-password`, mode 600, outside the repo).
- Address: `0xbdeb496b84d74806d631a51141144ef3a3d4a146`
- Network set to `testnet-bradbury` (chainId 4221, rpc https://rpc-bradbury.genlayer.com,
  mainContract 0x0112Bf6e83497965A5fdD6Dad1E447a6E004271D).
- Balance: 0 GEN. Faucet claim pending (human, Turnstile).

### Hello-world deploy + first non-deterministic transaction (studionet) — 2026-09-16 11:03–11:08 UTC

Contract: `spikes/hello.py` — one `gl.nondet.web.get`, one `gl.nondet.exec_prompt`,
custom validator via `gl.vm.run_nondet_unsafe` that re-runs the whole task and
compares HTTP status + LLM label. Lint: `genvm-lint check` passes.

**Attempt 1 — open-ended LLM output. FAILED consensus.**
- Deploy tx `0xe90658be906aa0e08096450e47ca5e8f48c95f369d0197165a73576bcabb6fa0`,
  contract `0x16523F6411472C18ae962d6129e16dE690f607a0`.
- `probe("https://example.com/")` tx
  `0x38ba14392e33719e5dd1a3f8d3c241c47fc1895916cba2aeec671e2f2749134a`
  → `MAJORITY_DISAGREE`, 4 rounds, 3 leader rotations, final `UNDETERMINED`.
  Prompt asked for "one lowercase word naming what the page is about".
- Per round (from `consensus_history`): leader gpt-5.4 → `domain`;
  leader gpt-oss → `example`; leader gemini → `documentation`; leader qwen →
  `example`. Validators (gemini-3-flash, qwen, gpt-oss, gemma, sonnet, …)
  disagreed each round. Every node executed successfully (`execution_result:
  SUCCESS`, LLM tokens billed) — this was a genuine comparison failure, not an
  infra error.
- Finding: studionet committees are **heterogeneous across model families**.
  Exact-match comparison of free-form LLM text will not reach consensus.

**Attempt 2 — constrained enum. PASSED consensus in one round.**
- Deploy tx `0x044d507cfcf487527e9b3f8aafa39325583cdb503adae5ef41512d3e0782cf43`,
  contract `0xAEacE8a3c40b62acE94C9b5C7131D669fCd69351`.
- Prompt: classify into one of `PLACEHOLDER | ERROR | NEWS | DOCS | OTHER`;
  label outside the enum raises `[LLM_ERROR]`.
- `probe("https://example.com/")` tx
  `0xb3fc3ea5c5f17a2bb6bf278a56d8ef75c466d07dde125cb57e461d4579f2543a`
  → `MAJORITY_AGREE`, 1 round, submitted 11:07:42, ACCEPTED by 11:07:53 (~11 s).
  Leader mistral → `PLACEHOLDER`. Validators gpt-5.4 and claude-sonnet-4.6
  each re-fetched and re-classified, stdout:
  `validator: leader=PLACEHOLDER/200 mine=PLACEHOLDER/200`. Two validators idle.
- `genlayer call … get` → `{last_status: 200, last_body_len: 559,
  last_topic: 'PLACEHOLDER', last_url: 'https://example.com/', runs: 1}`.
  State written on-chain from a real fetch and a real model inference.

Consequences for Circuit (recorded in PROGRESS.md):
1. Every LLM output that validators compare must be a closed enum or a bounded
   number. `verdict` ∈ {NO_ACTION, ELEVATED, RESTRICT, PAUSE} compared exactly;
   `confidence` compared with tolerance; `reasoning` stored but never compared.
2. `genlayer trace` is unavailable on studionet (`gen_dbg_traceTransaction`
   not found). Use `eth_getTransactionByHash` on the RPC and read
   `consensus_history.consensus_results[*]` — it exposes each round's leader
   model, `eq_outputs`, and each validator's vote and stdout. This is how the
   equivalence iteration in `docs/equivalence.md` will be evidenced.
3. Explorer: https://explorer-studio.genlayer.com/ (addresses above).

## Target network change: Studio Next (chain 61997) — 2026-09-16 11:20 UTC

Organisers' week-1 FAQ: the project **must** be deployed on Studio Next
(RPC https://studio-next.genlayer.com/api, chain ID 61997, explorer
https://explorer-studio-dev.genlayer.com/). Other networks do not satisfy the
requirement. Bradbury work is dropped; the faucet blocker is moot.

Verified facts (all executed, not read):
- `https://studio-next.genlayer.com/api` and `https://studio-dev.genlayer.com/api`
  both answer `eth_chainId` = `0xf22d` (61997). Same network, two hostnames.
  genlayer-js 2.0.0-rc.1 exports it as `studioDevnet`; CLI 0.40.0-rc.3 as `studio-dev`.
- Fees are enabled (`sim_getFeeConfig.enabled = true`, `genPerTimeUnit = 1`).
  Deploy without fees → `FeeValueMustBeNonZero(1)` (EVM tx
  `0x730fcb7b…783`). The CLI 0.40.0-rc.3 sends the same error *with*
  `--fee-value`, because it bundles an unreleased git commit of genlayer-js,
  not `2.0.0-rc.1`. Deploying through `genlayer-js@2.0.0-rc.1` directly
  (`scripts/deploy.cjs`, `estimateTransactionFees` → `deployContract({fees})`)
  works. **CLI is not used for Studio Next transactions.**
- `sim_fundAccount` returns a FINALIZED tx but `eth_getBalance` stays 0;
  the network nevertheless accepts transactions from the 0-GEN deployer and
  the balance afterwards reads ~0.0999 GEN (deposit refund accounting). Fee
  accounting on Studio Next is simulated; not a blocker.
- **GenVM is v0.3.0 on Studio Next.** The v0.2 header
  (`py-genlayer:1jb45aa8…`) is rejected: `invalid_contract runner malformed`
  (tx `0x2ec39dc1…4fef`). Required header, taken from Studio Next's own
  bundled examples:
  ```
  # v0.3.0
  # { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
  ```
- v0.3.0 API differs from the installed `genlayer-dev` skill and the v0.2 docs
  (migration guide: https://sdk.genlayer.com/main/executors/v0.3/python-sdk/migration-guide.html):
  `import genlayer as gl; from genlayer.types import *`; `gl.contract.Contract`;
  `gl.vm.run_nondet_unsafe` → **`gl.vm.run_nondet`** (unsafe) and old safe
  `run_nondet` → **`gl.vm.run_nondet_default`** (use this); `u256(...)` wrappers
  gone (plain ints); `gl.get_contract_at` → `gl.contract.get_at`;
  `gl.contract_interface` → `gl.contract.interface`; `gl.storage.TreeMap/DynArray`;
  `UserError.data` not `.message`; `on='accepted'` → `on='decided'`.
  Confirmed by execution: `run_nondet_unsafe` → `AttributeError` on-chain
  (tx `0x03b8c061…ce29`); `run_nondet_default` works.
- `genvm-lint 0.11.0` lints v0.3.0 contracts (3 checks pass) but cannot load
  the `5jycge…` runner for its validation step. Lint is still run; validation
  is done by the network.

### Hello-world on Studio Next — 2026-09-16 11:38–11:41 UTC

- Deploy tx `0xdd0c4ae73fdc8c2f92271c157722dba42ff0c9967c8d7e9aa89948c03cac925e`
  → contract **`0xA8E321f40c5230f9356e08F77420fF7FB06aE1D1`**, 4.3 s to decided,
  `FINISHED_WITH_RETURN`.
  Explorer: https://explorer-studio-dev.genlayer.com/address/0xA8E321f40c5230f9356e08F77420fF7FB06aE1D1
- `probe("https://example.com/")` tx
  `0xdd623724df526c2b66d4636c280f7b13c3956353cd13486ed72c37e4d9074765`
  → `MAJORITY_AGREE`, 1 round, 10.5 s, `FINISHED_WITH_RETURN`.
  Validators gpt-oss, gemini, gpt-5.4 each logged
  `validator: leader=PLACEHOLDER/200 mine=PLACEHOLDER/200`; one idle (quorum).
- `get()` → `{last_status: 200, last_body_len: 559, last_topic: 'PLACEHOLDER', runs: 1}`.

### Open: IC→EVM on Studio Next
Docs (messages page): "Studio: EVM contract interaction beyond value transfers
to EOAs is not implemented … Ghost contracts are not implemented." Studio Next
is still Studio. To be tested by execution next (spike 3); if confirmed, the
DemoVault becomes an Intelligent Contract paused via an IC→IC internal message.
