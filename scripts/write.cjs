// node scripts/write.cjs <address> <method> [json-args] [value-wei]
const { client, parseArgs, feesFor, feesForWrite, feesWithMessages, waitFinalized, requireSuccessful, summarize } = require("./gl.cjs");
(async () => {
  // --force: skip the simulating estimator so a call expected to revert is
  // still submitted and its failure lands on-chain as evidence.
  // --messages recipient:method[,…]: like --force, but with hand-built
  // internal-message allocations (see gl.cjs feesWithMessages).
  const argv = process.argv.slice(2);
  const force = argv.includes("--force");
  const mi = argv.indexOf("--messages");
  const messages = mi >= 0 ? argv[mi + 1] : null;
  const positional = argv.filter((a, i) => a !== "--force" && a !== "--messages" && (mi < 0 || i !== mi + 1));
  const [address, functionName, argsJson, valueWei] = positional;
  if (!address || !functionName) throw new Error("usage: write.cjs <address> <method> [json-args] [value-wei]");
  const { client: c, account } = client();
  const args = parseArgs(argsJson);
  const value = valueWei ? BigInt(valueWei) : undefined;
  const fees = messages ? await feesWithMessages(c, messages)
    : force ? await feesFor(c)
    : await feesForWrite(c, { account, address, functionName, args, value });
  const t0 = Date.now();
  const hash = await c.writeContract({ account, address, functionName, args, value, fees });
  console.log("tx", hash);
  const tx = await waitFinalized(c, hash);
  console.log("finalized in", ((Date.now() - t0) / 1000).toFixed(1), "s", JSON.stringify(summarize(tx)));
  const lr = tx.consensus_data?.leader_receipt; const L = Array.isArray(lr) ? lr[0] : lr;
  if (L?.genvm_result?.stdout) console.log("leader stdout:", L.genvm_result.stdout.trim());
  if (L?.genvm_result?.stderr) console.log("leader stderr:", L.genvm_result.stderr.trim().slice(0, 2000));
  for (const v of tx.consensus_data?.validators ?? []) {
    const m = v.node_config?.primary_model?.model || v.node_config?.model;
    console.log("validator", v.vote, m, "|", (v.genvm_result?.stdout || "").trim(), (v.genvm_result?.stderr || "").trim().slice(0, 300));
  }
  if (L?.result && typeof L.result === "string") console.log("leader result (b64):", L.result, "=", Buffer.from(L.result, "base64").toString("latin1").slice(1));
  requireSuccessful(tx);
})().catch((e) => { console.error("ERROR", e.shortMessage || e.message || e); process.exit(1); });
