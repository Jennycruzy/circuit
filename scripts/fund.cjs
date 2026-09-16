// node scripts/fund.cjs [amount]  — Studio-only faucet (sim_fundAccount)
const { client } = require("./gl.cjs");
(async () => {
  const amount = Number(process.argv[2] || 100);
  const { client: c, account } = client();
  const before = await c.getBalance({ address: account.address });
  const r = await c.fundAccount({ address: account.address, amount });
  console.log("fund result", r);
  await new Promise((r) => setTimeout(r, 4000));
  const after = await c.getBalance({ address: account.address });
  console.log("balance before", before.toString(), "after", after.toString());
})().catch((e) => { console.error("ERROR", e.shortMessage || e.message || e); process.exit(1); });
