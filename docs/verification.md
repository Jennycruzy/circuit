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
threshold at tier boundaries). Recorded in PROGRESS.md. The consensus spike (§3.3)
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
is still Studio. The deployed probe was called on 2026-09-16, but the target
address has no bytecode or GenLayer contract schema, so the result is not a
valid EVM interoperability test. The transaction remains unresolved; no
pause call was emitted.

## Audit review — 2026-09-16 14:35 UTC

This review records the checks performed after the previous project handoff.
It does not convert pending or missing network state into a result.

### Network and deployment

- JavaScript client: `genlayer-js 2.0.0-rc.1`; Studio-dev chain: 61997; RPC:
  `https://studio-dev.genlayer.com/api`.
- A live hello read returned `last_status: 200`, `last_body_len: 559`, and
  `runs: 1`. A live probe read returned an empty state.
- Public RPC checks returned no EVM bytecode for the hello contract, probe, or
  recorded target. The target's `gen_getContractCode` and
  `gen_getContractSchema` calls returned `Contract ... not found`; no target
  contract is deployed.

### Probe transaction

- The real `view_paused` call was submitted with hash
  `0xfc423a5653ae69efaaf6444a3a31535958b2fab2655acc60619cbcfe9681f27b`.
- The last inspection showed `PROPOSING`, `NOT_VOTED`, zero rounds, no
  consensus data, and no receipt. The helper later received HTML instead of
  JSON-RPC, so the transaction is unresolved and is not evidence that EVM
  calls work or fail.
- The EVM probe's `emit_pause` was not submitted because its recorded target
  was not deployed.

### SDK and documentation

- Current EVM docs confirm that `@gl.evm.contract_interface` is the documented
  interface for EVM view and write calls; that decorator is not a defect.
- Current messages docs say Studio does not implement EVM contract interaction
  beyond value transfers to EOAs, and external messages execute through Ghost
  only after finality. The Solidity/Ghost path cannot be claimed here.
- Current fee docs require a message fee budget for message-producing branches.
  `scripts/write.cjs` now uses `estimateTransactionFeesForWrite` and waits for
  finalization. The first pause simulation failed during contract execution
  before a transaction was submitted.

### DemoVault IC control attempt — 2026-09-16 14:35 UTC

- DemoVault deployment tx
  `0x3e47c0835891728daac2ad11bf438dfaf4c3045cb77a88ebff0ff6fc60eacfb1`
  finalized successfully and created
  `0xa0d10d68050f1f3f993ca99D3E150F95371886eB`.
  Explorer: https://explorer-studio-dev.genlayer.com/address/0xa0d10d68050f1f3f993ca99D3E150F95371886eB
- Pause-probe deployment tx
  `0x36626ac9327c64ffe48892a48a1c7a7cd9233c2c7e06c0daa880990ee9a10ecb`
  finalized successfully and created
  `0xEe750F2EEF9EDBC10551fF741a05a74C1A1173DB`.
  Explorer: https://explorer-studio-dev.genlayer.com/address/0xEe750F2EEF9EDBC10551fF741a05a74C1A1173DB
- `set_controller(probe)` finalized successfully in
  `0x34eb04162d06e4699ac0d6230a5382b27037e6ce34f449e7cb51e0df9900e57d`.
- The first `emit_pause` attempt did not submit a transaction. Both
  `estimateTransactionFeesForWrite` and a direct `gen_call` simulation returned
  an execution error. The structured receipt's leader stderr was:
  `AttributeError: module 'genlayer' has no attribute 'get_contract_at'`.
  The failed simulation made no state change.
- The current v0.3.0 runtime exports `gl.contract.get_at`, even though the
  current public messages page shows `gl.get_contract_at`. The probe source was
  corrected to the runtime API. Because the controller is one-time, the next
  live check must deploy a fresh vault and corrected probe, then inspect the
  resulting parent and child receipts.
- The direct contract suite passes 6 tests. `genvm-lint` passes its 3 static
  checks for each contract; its validation step cannot load the pinned v0.3.0
  runner archive in this environment.

## Spike 3 (Studio form): IC→IC control message — 2026-09-16 19:29–19:31 UTC

Studio Next has no EVM/Ghost path, so the main-spec §3.3 spike 3 is run in its
Studio-equivalent form: one Intelligent Contract emitting a write message to
another. This is the mechanism both `pause()` and `veto()` depend on.

Executed, all finalized, all `MAJORITY_AGREE`:
- Fresh DemoVault deploy `0x8c3f79e8aae8eb36a1e87f71bc823e0a436b1827c346ac7b9f58f6a66b88f454`
  → **`0x9Be50f5A958cF2807bbe51a3c99790466acd91CF`** (36.2 s).
- Corrected probe (`gl.contract.get_at(...).emit(on="finalized").pause()`)
  deploy `0xcbcbb0d41ab429752be01aef1ae63d8552e6d3d5196eee8fbe93eb84ad6535cd`
  → **`0x7C01caF67D90dE13C5512c8099DA4CF31452dF08`** (37.6 s).
- `set_controller(probe)` finalized (validators gpt-5.4, mistral, deepseek agree).
- `emit_pause()` parent tx
  **`0x329936492ee6e5a543370706eeacce96b738fe4a0a53398d0b8a51333eaa25f8`**,
  created 19:30:23 UTC, finalized in 35.8 s, `FINISHED_WITH_RETURN`.
  Receipt `messages[0]` = `{recipient: vault, data: "DgAscGF1c2U=" (= calldata
  `pause`), onAcceptance: false}`; `triggered_transactions` =
  [`0x2421ab04e89e48bbb6dd9848b6a9c3311bd5e12a300cd9f96db3351a06f1870c`].
- Child tx `0x2421ab04…870c`: `from` = probe, `to` = vault,
  `triggered_by` = parent, `triggered_on: "finalized"`, created 19:30:55 UTC
  (**32 s after the parent was submitted**), `FINISHED_WITH_RETURN`,
  `MAJORITY_AGREE`.
- Vault `get_state()` afterwards:
  `{paused: true, pause_count: 1, last_action: "paused", controller: probe}`.
  Probe `get_state()`: `{emitted: true}`.

Conclusions:
1. **PROVEN.** An Intelligent Contract can change another Intelligent
   Contract's state through `gl.contract.get_at(addr).emit(on="finalized").method()`.
   The sender seen by the callee is the emitting contract's address, so the
   callee's `controller`/`circuit` authorisation check works as designed.
2. The message is delivered only on finality of the parent. Measured
   parent-submit → child-created latency: ~32 s on Studio Next (parent
   finalization ~36 s on this network with 0 appeal rounds). This is the
   "ACT is not instantaneous" cost from divergence 2, now with a number.
3. `gl.get_contract_at` (as printed on the public messages page) does not
   exist in the v0.3.0 runtime; `gl.contract.get_at` does. Confirmed by the
   earlier failed simulation and this successful execution.
4. The message fee budget for a message-producing branch must be estimated
   with `estimateTransactionFeesForWrite` (messageFees `120000000000010352`
   consumed here); `scripts/write.cjs` already does this.

## Addendum A §A2.7 — governance-path blockers — 2026-09-16 19:45–20:05 UTC

Probe: `spikes/gov_probe.py`, deployed at
**`0xf4c67DA52A2e460E723105bE73fc703438B01c21`** (tx
`0xe52c1a6ae37ea56db4ff2e7002819fea337fda6b8197bda7fbd7094009a2bab1`).
All read checks are live `gen_call` results via `scripts/read.cjs`; the write
check is a finalized transaction.

- [x] **Calldata decoding inside GenVM.** `env()` on-chain:
  `eth_abi`, `eth_utils`, `web3` → `ModuleNotFoundError`. Available:
  `genlayer.calldata` (GenVM native codec), `genlayer.evm.calldata`
  (ABI codec with `selector_of`/`MethodEncoder`), `hashlib`, `json`, `re`,
  `base64`, `datetime`. `Keccak256(b"pause()")[:4]` = `8456cb59` — the real
  EVM selector, computed in-VM. **Decision:** on Studio Next the governor's
  targets are Intelligent Contracts, so a proposal's calldata *is* GenVM
  calldata (`{'': method, 'args': [...]}`), the same bytes the message
  system itself carries (receipt `messages[0].data` = `0e002c7061757365` =
  `pause`, byte-identical to `genlayer_py.abi.calldata.encode` off-chain).
  Circuit decodes it with `gl.calldata.decode` — a real in-VM decode, no
  hand-rolled selector map needed. `decode_calldata(bytes)` returned
  `{method: "set_owner", args: ["0x1111…"], types: ["Address"]}` for a
  proposer-built blob, and a clean `DecodingError: unexpected end of memory`
  for `0xdeadbeef` (so "undecodable" is a first-class, reportable state).
  "Unknown selector" becomes "method not in the target's registered
  interface", which Circuit reports explicitly.
- [x] **Reading another contract's state from an Intelligent Contract.**
  `gl.contract.get_at(Address(x)).view().get_state()` executed inside a view
  returned the live DemoVault dict (`paused: true, controller: 0x7C01…`).
  Syntax confirmed from the v0.3 SDK source: `Proxy.view(state=, catch_vm_error=)`
  then `__getattr__(method)(*args)`; dynamic method names therefore work
  (`getattr(proxy.view(), name)(*args)`), and likewise for `emit()`.
- [x] **Struct/array returns.** `shapes()` returned `list[str]` of addresses,
  `list[bytes]` (rendered `0x…` by genlayer-js), `list[dict]`, and a 200-bit
  int (as a decimal string) without loss. A `bytes` *argument* round-trips
  from genlayer-js as `Uint8Array` (`scripts/gl.cjs parseArgs`, marker
  `{"$bytes": "0x…"}`). DemoGovernor getters will return plain dicts/lists.
- [x] **Two targets from one contract.** `emit_two(A, B)` tx
  `0x2b0c395510897ab4c1c6f4e33712af521b9a29107394d374dc09135b58a4e5ab`
  (finalized 35.8 s) produced two `messages` and two
  `triggered_transactions` (`0x1e713871…6d04`, `0x22081f6b…2f38`); both
  vaults `0x1Fd8020B…8173` and `0x7F74cb25…c3aa` read `paused: true,
  pause_count: 1`. One Intelligent Contract can control both DemoVault and
  DemoGovernor.

Not fatal, but noted: `emit(on="finalized")` is the only phase used so far;
`on="decided"` is documented and would cut ~30 s off ACT latency at the cost of
acting before the appeal window closes. Decision deferred to the equivalence
iteration (`docs/equivalence.md`).

## DemoGovernor live — 2026-09-16 19:50–20:20 UTC

Contracts (`contracts/demo_vault.py` v2 with owner surface, `contracts/demo_governor.py`):
18 direct tests pass (`tests/direct/`), using a multi-contract harness in
`tests/direct/conftest.py` that routes `CallContract`, records
`EmitInternalMessage`/`EmitEvent`, gives each contract its own storage, and
syncs `gl.message.raw["datetime"]` on `warp`. The stock direct VM does none
of those; the network is the authority for all of them.

**Timing finding (real, changes the deployment config).** First live governor
`0xf5266d59CA253B7619198293ae20BA1A56CdCf09` was deployed with a 30 s voting
period. `propose` (tx `0x2d1a12bc…d5ea`) carried `created_at 1789588402`; the
`vote` submitted immediately after finality (tx `0x2523999f…7590`) carried
`19:54:02` — 40 s later — and finished `FINISHED_WITH_ERROR` with user error
`voting closed`. Every transaction on Studio Next takes ~36–55 s to finality
and its datetime is fixed at creation, so any governor window must be
several multiples of that. Redeployed as
**`0x16C1958C6833CA255dCDDF0dd99b90a31AAAfA6e`** with voting 180 s /
timelock 300 s / quorum 10 %; fresh vault
**`0x9804c9624DcbF3f42d13990d1736E21E7a50B570`**, `set_owner(governor)` tx
`0xf51da748…8a2b`, `set_circuit(probe 0x59e31b12…2C1c)` tx `0x4d6ec30b…99fd`,
`grant_power(deployer, 100)` tx `0x3a203516…bccc`.

`gl.message.raw["datetime"]` parses with `datetime.fromisoformat` on the live
runtime (`get_config().now` returned a unix timestamp; `created_at` matched
the receipt's `created_at` to the second).

Hostile proposal #0: target = vault, calldata
`0x16004c…dead` = `set_owner(0x…dEaD)`, description "Adjust fee parameter".
`propose` tx `0x7a1a27d8…42ed`, `vote(0, true)` tx `0xe8d22ec0…4f11` →
`for_votes 100`, `state ACTIVE`, `voting_ends 1789588889`.

### Veto from a contract, and execute-after-veto — 2026-09-16 20:02–20:06 UTC

- The first `queue(0)` attempt was refused at fee estimation (`execution
  failed`): the estimator's simulated datetime lagged the real clock and hit
  `voting still open`. `scripts/write.cjs --force` now bypasses the
  simulating estimator (generic fee quote) so that a call expected to revert
  is still submitted and its failure is on-chain evidence.
- **Veto (A4 step 5) PROVEN.** Probe `emit_veto(governor, 0)` parent tx
  `0x7266dc7d333a704270bba30b4ef0ea0c24a7382574e0e0cd407ddb1a24b1b01f`
  (finalized 36.2 s) → child
  `0x405b5039449101c4cc6e3006f27eeceb95deed116d8e44f9dcff36ee24a188ad`
  → proposal 0 `state: VETOED`. The governor's `only circuit may veto`
  check passed because the message sender is the bound contract address.
- **Execute after veto reverts on-chain.** `execute(0)` tx
  `0xf3949f43739e2c3238a64a133830ccd6504abfd6658f53a25dc823d16e758253`,
  `FINISHED_WITH_ERROR`, leader result = user error `proposal was vetoed`,
  `messages: []`, no child transactions. Vault `0x9804c962…B570` still reads
  `owner: 0x16C1958C…fA6e` (the governor), `fee_bps: 0`. The hostile
  `set_owner(0x…dEaD)` never reached the vault.
- Benign proposal #1 (`set_fee_bps(30)`, "Set protocol fee to 0.30% (30
  bps)"): `propose` tx `0x34a803b7…4d08`, `vote(1,true)` tx `0x1a2b6984…1fe7`;
  queue/execute recorded below when the windows elapse.
