import { createClient, studioDevnet } from "./lib.js";

const cfg = await (await fetch("./config.json")).json();
const chain = { ...studioDevnet, rpcUrls: { default: { http: [cfg.rpc] } } };
const readClient = createClient({ chain });
const $ = (id) => document.getElementById(id);
const explorer = cfg.explorer || "https://explorer-studio-dev.genlayer.com";
const operator = cfg.operator_set || { circuit: cfg.circuit, protocol_id: cfg.protocol_id };
const chainId = Number(studioDevnet.id || 61997);
const chainHex = "0x" + chainId.toString(16);
const wei = 10n ** 18n;
const compact = (x) => x ? x.slice(0, 8) + "…" + x.slice(-6) : "—";
const equal = (a, b) => String(a || "").toLowerCase() === String(b || "").toLowerCase();
const esc = (x) => String(x ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const gen = (x) => { try { return (Number(BigInt(x)) / 1e18).toFixed(4) + " GEN"; } catch { return "—"; } };
const address = (x) => x ? '<span class="address">' + esc(compact(x)) + "</span>" : "—";
const tx = (x) => x ? '<a href="' + explorer + "/tx/" + encodeURIComponent(x) + '" target="_blank" rel="noopener">' + esc(compact(x)) + "</a>" : "—";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let provider, signer, account = "", config, wallet = { bond: 0n, chainId: null }, pending = false;

function chip(id, text, type) { const e = $(id); e.textContent = text; e.className = "status-chip" + (type ? " " + type : ""); }
function log(title, body, type) {
  const stream = $("activity-log");
  if (stream.querySelector(".empty")) stream.innerHTML = "";
  const e = document.createElement("div");
  e.className = "log-entry " + (type || "pending");
  e.innerHTML = '<div class="log-entry-top"><strong>' + esc(title) + '</strong><span>' + new Date().toISOString().replace("T", " ").slice(0, 19) + ' UTC</span></div><p>' + body + "</p>";
  stream.prepend(e);
  return e;
}
function logUpdate(e, body, type) { e.className = "log-entry " + type; e.querySelector("p").innerHTML = body; }
async function read(addressValue, method, args) {
  let error;
  for (let i = 0; i < 3; i += 1) {
    try { return await readClient.readContract({ address: addressValue, functionName: method, args: args || [] }); }
    catch (x) { error = x; if (i < 2) await sleep(250 * (i + 1)); }
  }
  throw error;
}
function amount(text) {
  if (!/^\d+(\.\d{1,18})?$/.test(String(text).trim())) throw new Error("Enter a valid GEN amount.");
  const p = String(text).trim().split(".");
  return BigInt(p[0]) * wei + BigInt(((p[1] || "") + "0".repeat(18)).slice(0, 18));
}
function integer(id, label, allowZero) {
  const text = $(id).value.trim();
  if (!/^\d+$/.test(text) || (!allowZero && BigInt(text) === 0n)) throw new Error(label + " must be a " + (allowZero ? "non-negative" : "positive") + " integer.");
  return BigInt(text);
}
function ready() {
  const connected = Boolean(account && signer && wallet.chainId === chainId);
  const bonded = connected && config && wallet.bond >= BigInt(config.bond);
  const deployer = connected && config && equal(account, config.deployer);
  const rules = { "post-bond": connected, "assess-drain": bonded, "assess-proposal": bonded, "withdraw-bond": connected && wallet.bond > 0n, "register-protocol": deployer, "update-protocol": deployer };
  Object.keys(rules).forEach((id) => { const b = $(id); b.dataset.ready = rules[id] ? "true" : "false"; b.disabled = pending || !rules[id]; });
  chip("actions-status", connected ? (bonded ? "bonded / ready" : "bond required") : "locked", connected ? (bonded ? "ok" : "warn") : "");
  chip("register-status", deployer ? "deployer verified" : "deployer only", deployer ? "ok" : "warn");
  $("register-help").textContent = deployer ? "Deployer verified. Ready to register or update." : connected ? "Connected wallet is not the Circuit deployer." : "Connect the deployer wallet to enable.";
}
function render() {
  if (config) {
    $("circuit-address").innerHTML = address(operator.circuit);
    $("terminal-circuit").textContent = compact(operator.circuit);
    $("deployer-address").innerHTML = address(config.deployer);
    $("governor-address").innerHTML = address(config.governor);
    $("required-bond").textContent = gen(config.bond);
    $("bond-help").textContent = gen(config.bond);
    $("bond-amount").value = (Number(BigInt(config.bond)) / 1e18).toFixed(4);
    const rows = [["deployer", address(config.deployer), "May register and update protected protocols."], ["governor", address(config.governor), "Bound governance contract."], ["high confidence", config.high_confidence + "/100", "Committee confidence floor."], ["quorum threshold", (Number(config.quorum_threshold_bps) / 100).toFixed(2) + "%", "Turnout floor for hostile proposals."], ["assessment bond", gen(config.bond), "Minimum bond for either assessment path."], ["slash on NO_ACTION", (Number(config.slash_bps) / 100).toFixed(2) + "%", "Bond fraction sent to treasury."], ["proposal assessments", config.proposal_assessment_count, "Stored governance receipts."], ["drain assessments", config.assessment_count, "Stored protocol receipts."], ["treasury", gen(config.treasury), "Accumulated slashed bonds."]];
    $("config-table").innerHTML = rows.map((r) => "<tr><td>" + esc(r[0]) + "</td><td>" + r[1] + "</td><td>" + esc(r[2]) + "</td></tr>").join("");
  }
  $("wallet-address").innerHTML = account ? address(account) : "No wallet connected";
  $("wallet-tag").textContent = account ? compact(account) : "wallet disconnected";
  $("wallet-tag").className = "tag" + (account ? " green" : "");
  $("wallet-bond").textContent = account ? gen(wallet.bond) : "—";
  $("withdraw-amount").textContent = account ? gen(wallet.bond) : "—";
  if (!account) { $("network-status").textContent = "Connect an injected wallet to check the signing network."; $("console-status").textContent = "LOCKED"; $("console-status").className = "orange"; chip("access-status", "wallet required", ""); $("terminal-role").textContent = "CONNECT WALLET"; }
  ready();
}
async function syncWallet() {
  if (!account || !provider) return;
  wallet.chainId = Number.parseInt(await provider.request({ method: "eth_chainId" }), 16);
  if (wallet.chainId !== chainId) { wallet.bond = 0n; $("network-status").textContent = "Wrong network: wallet is on chain " + wallet.chainId + "; switch to " + chainId + "."; chip("access-status", "wrong network", "bad"); $("console-status").textContent = "WRONG NETWORK"; $("console-status").className = "orange"; render(); return; }
  $("network-status").textContent = "Studio Next verified · chain " + chainId + " · wallet may sign live operations.";
  chip("access-status", "wallet ready", "ok"); $("console-status").textContent = "READY"; $("console-status").className = "lime";
  wallet.bond = config ? BigInt(await read(operator.circuit, "bond_of", [account])) : 0n;
  const isDeployer = config && equal(account, config.deployer);
  $("terminal-role").textContent = isDeployer ? "DEPLOYER / OPERATOR" : "ASSESSOR / OPERATOR";
  $("terminal-role").className = isDeployer ? "lime" : "blue";
  render();
}
async function switchNetwork() {
  if (await provider.request({ method: "eth_chainId" }) === chainHex) return;
  try { await provider.request({ method: "wallet_switchEthereumChain", params: [{ chainId: chainHex }] }); }
  catch (e) { if (!e || e.code !== 4902) throw e; await provider.request({ method: "wallet_addEthereumChain", params: [{ chainId: chainHex, chainName: chain.name || "Studio Next", rpcUrls: [cfg.rpc], nativeCurrency: { name: "GEN", symbol: "GEN", decimals: 18 }, blockExplorerUrls: [explorer] }] }); await provider.request({ method: "wallet_switchEthereumChain", params: [{ chainId: chainHex }] }); }
}
async function connect() {
  if (!window.ethereum) { log("Wallet unavailable", "Install MetaMask or another EIP-1193 wallet, then reload this console.", "error"); return; }
  provider = window.ethereum;
  try { $("console-status").textContent = "CONNECTING…"; const accounts = await provider.request({ method: "eth_requestAccounts" }); if (!accounts || !accounts[0]) throw new Error("The wallet returned no account."); await switchNetwork(); account = accounts[0]; signer = createClient({ chain, account, provider }); await syncWallet(); log("Wallet connected", esc(compact(account)) + " · Studio Next chain " + chainId + ".", "success"); }
  catch (e) { $("console-status").textContent = "LOCKED"; $("console-status").className = "orange"; log("Wallet connection failed", esc(e && e.message ? e.message : e), "error"); }
}
async function refresh() {
  try {
    config = await read(operator.circuit, "get_config");
    const id = $("assess-protocol").value.trim() || operator.protocol_id;
    const protocol = await read(operator.circuit, "get_protocol", [id]);
    $("protocol-state").innerHTML = esc(protocol.protocol_id) + " · target " + address(protocol.target) + " · threshold " + (Number(protocol.drain_threshold_bps) / 100).toFixed(2) + "% · window " + protocol.window_s + "s";
    $("baseline-state").innerHTML = gen(protocol.baseline_balance) + " at " + new Date(Number(protocol.baseline_at) * 1000).toISOString() + " · " + protocol.evidence_sources.length + " evidence source(s)";
    render(); if (account) await syncWallet();
  } catch (e) { $("config-table").innerHTML = '<tr><td colspan="3" class="empty">Unable to read Circuit: ' + esc(e && e.message ? e.message : e) + "</td></tr>"; log("Circuit read failed", esc(e && e.message ? e.message : e), "error"); }
}
async function write(method, args, value, title) {
  if (!signer || !account) throw new Error("Connect a wallet before signing an operation.");
  if (wallet.chainId !== chainId) throw new Error("Switch the wallet to Studio Next chain " + chainId + ".");
  const item = log(title, "Preparing an authoritative fee estimate…", "pending"); pending = true; ready();
  try {
    const fees = await signer.estimateTransactionFeesForWrite({ address: operator.circuit, functionName: method, args, value: value || 0n });
    logUpdate(item, "Fee estimate ready. Approve the transaction in your wallet…", "pending");
    const hash = await signer.writeContract({ address: operator.circuit, functionName: method, args, value: value || 0n, fees });
    $("terminal-tx").textContent = compact(hash); logUpdate(item, "Submitted " + tx(hash) + ". Waiting for contract finality…", "pending");
    const receipt = await signer.waitForFinalization({ hash, retries: 100, interval: 3000 });
    logUpdate(item, "Finalized " + tx(hash) + " · " + esc(receipt && (receipt.txExecutionResultName || receipt.result_name || receipt.statusName || "confirmed")) + ".", "success");
    await refresh(); return receipt;
  } catch (e) { logUpdate(item, esc(e && e.message ? e.message : e), "error"); throw e; }
  finally { pending = false; ready(); }
}
function action(id, fn) { $(id).addEventListener("click", async () => { if (pending) return; try { await fn(); } catch (e) { log("Operation blocked", esc(e && e.message ? e.message : e), "error"); } }); }
action("post-bond", async () => { const v = amount($("bond-amount").value); if (!config || v < BigInt(config.bond)) throw new Error("Use at least " + gen(config.bond) + " to make an assessment eligible."); await write("post_bond", [], v, "Post assessment bond"); });
action("assess-drain", async () => { const id = $("assess-protocol").value.trim(); if (!id) throw new Error("Enter a protocol id."); if (wallet.bond < BigInt(config.bond)) throw new Error("Post the required bond first."); await write("assess", [id], 0n, "Assess " + id); });
action("assess-proposal", async () => { const id = integer("proposal-id", "Proposal id", true); if (wallet.bond < BigInt(config.bond)) throw new Error("Post the required bond first."); await write("assess_proposal", [id], 0n, "Assess proposal #" + id); });
action("withdraw-bond", async () => { if (wallet.bond <= 0n) throw new Error("There is no available bond to withdraw."); if (window.confirm("Withdraw the available bond for this wallet?")) await write("withdraw_bond", [], 0n, "Withdraw assessment bond"); });
$("update-form").addEventListener("submit", async (event) => {
  event.preventDefault(); if (pending) return;
  try {
    if (!config || !equal(account, config.deployer)) throw new Error("Only the Circuit deployer can update a protocol.");
    const id = $("update-id").value.trim(), target = $("update-target").value.trim(), threshold = integer("update-threshold", "Threshold", false), seconds = integer("update-window", "Window", false), criteria = $("update-criteria").value.trim(), sources = $("update-sources").value.split("\n").map((x) => x.trim()).filter(Boolean), reset = $("reset-baseline").checked;
    if (!id || !/^0x[0-9a-fA-F]{40}$/.test(target)) throw new Error("Enter a protocol id and a valid target address.");
    if (threshold > 10000n) throw new Error("Threshold cannot exceed 10000 bps.");
    if (!criteria || !sources.length || sources.some((x) => !/^https?:\/\//i.test(x))) throw new Error("Criteria and at least one HTTP(S) source are required.");
    if (window.confirm("Update " + id + "? Reset the baseline: " + reset + ".")) await write("update_protocol", [id, target, threshold, seconds, JSON.stringify(sources), criteria, reset], 0n, "Update " + id);
  } catch (e) { log("Configuration update blocked", esc(e && e.message ? e.message : e), "error"); }
});
$("register-form").addEventListener("submit", async (event) => {
  event.preventDefault(); if (pending) return;
  try {
    if (!config || !equal(account, config.deployer)) throw new Error("Only the Circuit deployer can register a protocol.");
    const id = $("protocol-id").value.trim(), target = $("target-address").value.trim(), threshold = integer("threshold-bps", "Threshold", false), seconds = integer("window-seconds", "Window", false), criteria = $("criteria").value.trim(), sources = $("evidence-sources").value.split("\n").map((x) => x.trim()).filter(Boolean);
    if (!id || !/^0x[0-9a-fA-F]{40}$/.test(target)) throw new Error("Enter a protocol id and a valid target address.");
    if (threshold > 10000n) throw new Error("Threshold cannot exceed 10000 bps.");
    if (!criteria || !sources.length || sources.some((x) => !/^https?:\/\//i.test(x))) throw new Error("Criteria and at least one HTTP(S) source are required.");
    if (window.confirm("Register " + id + " against " + target + "?")) await write("register_protocol", [id, target, threshold, seconds, JSON.stringify(sources), criteria], 0n, "Register " + id);
  } catch (e) { log("Registration blocked", esc(e && e.message ? e.message : e), "error"); }
});
$("connect-wallet").addEventListener("click", connect);
$("connect-wallet-top").addEventListener("click", connect);
$("refresh").addEventListener("click", () => { if (!pending) refresh(); });
$("assess-protocol").addEventListener("change", () => refresh());
if (window.ethereum && window.ethereum.on) {
  window.ethereum.on("accountsChanged", (xs) => { account = xs && xs[0] ? xs[0] : ""; signer = account ? createClient({ chain, account, provider: window.ethereum }) : null; syncWallet().catch((e) => log("Wallet state error", esc(e && e.message ? e.message : e), "error")); });
  window.ethereum.on("chainChanged", () => syncWallet().catch((e) => log("Network state error", esc(e && e.message ? e.message : e), "error")));
}
function renderIndexedReceipts() {
  const receipts = cfg.operator_receipts || [];
  if (!receipts.length) return;
  const stream = $("activity-log");
  stream.innerHTML = "";
  for (const receipt of receipts) {
    const e = document.createElement("div");
    e.className = "log-entry success";
    const top = document.createElement("div");
    top.className = "log-entry-top";
    const title = document.createElement("strong");
    title.textContent = receipt.title;
    const stamp = document.createElement("span");
    stamp.textContent = "indexed on Studio Next";
    top.append(title, stamp);
    const p = document.createElement("p");
    p.textContent = receipt.note + " · " + receipt.tx.slice(0, 10) + "… · SUCCESS";
    e.append(top, p);
    stream.append(e);
  }
}
renderIndexedReceipts();
$("circuit-address").textContent = compact(operator.circuit);
refresh();
