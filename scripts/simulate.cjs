// node scripts/simulate.cjs <address> <method> [json-args]
// Simulates a write through sim_call and prints the leader receipt, so a
// failing estimate can be diagnosed without submitting anything.
const { client, parseArgs } = require("./gl.cjs");
(async () => {
  const [address, functionName, argsJson] = process.argv.slice(2);
  const { client: c, account } = client();
  try {
    const r = await c.simulateWriteContract({ account, address, functionName, args: parseArgs(argsJson), includeReceipt: true });
    console.log(JSON.stringify(r, (k, v) => typeof v === "bigint" ? v.toString() : v, 1).slice(0, 4000));
  } catch (e) {
    const s = JSON.stringify(e.details || e.cause || e, (k, v) => typeof v === "bigint" ? v.toString() : v);
    console.log("ERR", e.shortMessage || e.message);
    for (const m of (s || "").matchAll(/"(stderr|stdout|result|error_message|message)":"([^"]{0,800})/g)) console.log(m[1], "=>", m[2].slice(-700));
  }
})();
