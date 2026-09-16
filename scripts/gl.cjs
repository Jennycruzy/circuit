// Shared client for Studio Next (chain 61997) using genlayer-js 2.0.0-rc.1.
// The deployer key is decrypted from the CLI keystore at runtime; it never
// touches disk in plain form.
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFileSync } = require("child_process");
const { createClient, createAccount, isSuccessful } = require("genlayer-js");
const { studioDevnet } = require("genlayer-js/chains");

const KEYSTORE = path.join(os.homedir(), ".genlayer/keystores/circuit-deployer.json");
const PASSFILE = path.join(os.homedir(), ".circuit-keystore-password");
const VENV_PY = path.join(os.homedir(), ".venv-circuit/bin/python");

function privateKey() {
  if (process.env.CIRCUIT_PRIVATE_KEY) return process.env.CIRCUIT_PRIVATE_KEY;
  const py = `
import json,sys
from eth_account import Account
ks=json.load(open(sys.argv[1])); pw=open(sys.argv[2]).read().strip()
print(Account.decrypt(ks, pw).hex())`;
  const out = execFileSync(VENV_PY, ["-c", py, KEYSTORE, PASSFILE]).toString().trim();
  return out.startsWith("0x") ? out : "0x" + out;
}

function client() {
  const account = createAccount(privateKey());
  const c = createClient({ chain: studioDevnet, account });
  return { client: c, account };
}

async function feesFor(c, opts = {}) {
  const est = await c.estimateTransactionFees(opts);
  return { distribution: est.distribution, messageAllocations: est.messageAllocations, feeValue: est.feeValue, policy: est.policy };
}

async function waitDecided(c, hash) {
  const tx = await c.waitForTransactionReceipt({ hash, waitUntil: "decided", retries: 300, interval: 3000 });
  return tx;
}

function summarize(tx) {
  return {
    hash: tx.hash,
    status: tx.statusName || tx.status,
    result: tx.txExecutionResultName || tx.result_name || tx.txExecutionResult,
    successful: (() => { try { return isSuccessful(tx); } catch { return undefined; } })(),
    contract: tx.txDataDecoded?.contractAddress || tx.data?.contract_address,
    rounds: tx.num_of_rounds,
    resultName: tx.result_name,
  };
}

module.exports = { client, feesFor, waitDecided, summarize, studioDevnet, isSuccessful };
