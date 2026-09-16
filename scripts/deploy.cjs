// node scripts/deploy.cjs <contract.py> [json-args]
const fs = require("fs");
const { client, feesFor, waitDecided, summarize } = require("./gl.cjs");

(async () => {
  const [file, argsJson] = process.argv.slice(2);
  if (!file) throw new Error("usage: deploy.cjs <contract.py> [json-args]");
  const { client: c, account } = client();
  const args = argsJson ? JSON.parse(argsJson) : [];
  const code = new Uint8Array(fs.readFileSync(file));
  const bal = await c.getBalance({ address: account.address });
  console.log("deployer", account.address, "balance", bal.toString());
  const fees = await feesFor(c);
  console.log("fee quote", JSON.stringify(fees, (k, v) => (typeof v === "bigint" ? v.toString() : v)));
  const t0 = Date.now();
  const hash = await c.deployContract({ code, args, fees });
  console.log("deploy tx", hash);
  const tx = await waitDecided(c, hash);
  console.log("decided in", ((Date.now() - t0) / 1000).toFixed(1), "s", JSON.stringify(summarize(tx)));
  if (tx.txExecutionResultName && tx.txExecutionResultName !== "FINISHED_WITH_RETURN") {
    console.log("leader receipt", JSON.stringify(tx.consensus_data?.leader_receipt?.[0]?.genvm_result ?? tx.consensus_data?.leader_receipt?.genvm_result));
  }
})().catch((e) => { console.error("ERROR", e.shortMessage || e.message || e); process.exit(1); });
