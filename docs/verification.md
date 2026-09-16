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
