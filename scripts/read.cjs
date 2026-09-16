// node scripts/read.cjs <address> <method> [json-args]
const { publicClient, parseArgs } = require("./gl.cjs");
(async () => {
  const [address, functionName, argsJson] = process.argv.slice(2);
  const { client: c } = publicClient();
  const r = await c.readContract({ address, functionName, args: parseArgs(argsJson) });
  console.log(JSON.stringify(r, (k, v) => (typeof v === "bigint" ? v.toString() : v), 2));
})().catch((e) => { console.error("ERROR", e.shortMessage || e.message || e); process.exit(1); });
