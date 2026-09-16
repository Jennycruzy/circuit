// node scripts/read.cjs <address> <method> [json-args]
const { client } = require("./gl.cjs");
(async () => {
  const [address, functionName, argsJson] = process.argv.slice(2);
  const { client: c } = client();
  const r = await c.readContract({ address, functionName, args: argsJson ? JSON.parse(argsJson) : [] });
  console.log(JSON.stringify(r, (k, v) => (typeof v === "bigint" ? v.toString() : v), 2));
})().catch((e) => { console.error("ERROR", e.shortMessage || e.message || e); process.exit(1); });
