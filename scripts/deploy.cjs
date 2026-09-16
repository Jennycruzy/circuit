// node scripts/deploy.cjs <contract.py> [json-args]
const fs = require("fs");
const { client, feesFor, waitFinalized, requireSuccessful, summarize } = require("./gl.cjs");

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
  const hash = await c.deployContract({ account, code, args, fees });
  console.log("deploy tx", hash);
  const tx = await waitFinalized(c, hash);
  console.log("finalized in", ((Date.now() - t0) / 1000).toFixed(1), "s", JSON.stringify(summarize(tx)));
  requireSuccessful(tx);
})().catch((e) => { console.error("ERROR", e.shortMessage || e.message || e); process.exit(1); });
