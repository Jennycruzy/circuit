// node scripts/write.cjs <address> <method> [json-args] [value-wei]
const { client, feesForWrite, waitFinalized, requireSuccessful, summarize } = require("./gl.cjs");
(async () => {
  const [address, functionName, argsJson, valueWei] = process.argv.slice(2);
  if (!address || !functionName) throw new Error("usage: write.cjs <address> <method> [json-args] [value-wei]");
  const { client: c, account } = client();
  const args = argsJson ? JSON.parse(argsJson) : [];
  const value = valueWei ? BigInt(valueWei) : undefined;
  const fees = await feesForWrite(c, { account, address, functionName, args, value });
  const t0 = Date.now();
  const hash = await c.writeContract({ account, address, functionName, args, value, fees });
  console.log("tx", hash);
  const tx = await waitFinalized(c, hash);
  console.log("finalized in", ((Date.now() - t0) / 1000).toFixed(1), "s", JSON.stringify(summarize(tx)));
  requireSuccessful(tx);
  const lr = tx.consensus_data?.leader_receipt; const L = Array.isArray(lr) ? lr[0] : lr;
  if (L?.genvm_result?.stdout) console.log("leader stdout:", L.genvm_result.stdout.trim());
  if (L?.genvm_result?.stderr) console.log("leader stderr:", L.genvm_result.stderr.trim().slice(0, 2000));
  for (const v of tx.consensus_data?.validators ?? []) {
    const m = v.node_config?.primary_model?.model || v.node_config?.model;
    console.log("validator", v.vote, m, "|", (v.genvm_result?.stdout || "").trim(), (v.genvm_result?.stderr || "").trim().slice(0, 300));
  }
})().catch((e) => { console.error("ERROR", e.shortMessage || e.message || e); process.exit(1); });
