import { createClient, studioDevnet, calldata } from "./lib.js";

const cfg = await (await fetch("./config.json")).json();
const client = createClient({ chain: { ...studioDevnet, rpcUrls: { default: { http: [cfg.rpc] } } } });
const $ = (id) => document.getElementById(id);
const short = (a) => a ? a.slice(0, 6) + "…" + a.slice(-4) : "";
const name = (a) => cfg.contract_names[a] || short(a);
const addrLink = (a) => `<a href="${cfg.explorer}/address/${a}" target="_blank" rel="noopener" title="${a}">${name(a)}</a>`;
const ts = (t) => t ? new Date(t * 1000).toISOString().replace("T", " ").slice(0, 19) + " UTC" : "—";
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function read(address, functionName, args = []) {
  return client.readContract({ address, functionName, args });
}

// Decode raw GenVM calldata (as the governor stores it) into a plain call string.
function decodeAction(target, hex) {
  try {
    const bytes = Uint8Array.from((hex.replace(/^0x/, "").match(/../g) || []).map((h) => parseInt(h, 16)));
    const d = calldata.decode(bytes);
    const method = d instanceof Map ? d.get("") : d?.[""];
    const args = (d instanceof Map ? d.get("args") : d?.args) || [];
    if (typeof method !== "string") return { ok: false, text: `undecodable (${bytes.length} bytes)` };
    const fmt = (a) => (a && a.bytes) ? "0x" + Array.from(a.bytes, (b) => b.toString(16).padStart(2, "0")).join("")
      : a instanceof Uint8Array ? "0x" + Array.from(a, (b) => b.toString(16).padStart(2, "0")).join("")
      : typeof a === "bigint" ? a.toString() : JSON.stringify(a);
    return { ok: true, method, text: `${name(target)}.${method}(${args.map(fmt).join(", ")})` };
  } catch (e) {
    return { ok: false, text: `undecodable: ${e.message}` };
  }
}

let proposals = [], assessments = [], drains = [], protocol = null, byProposal = new Map(), now = 0, gcfg = {};

function verdictPill(pid) {
  const a = byProposal.get(pid);
  return a ? `<span class="pill ${a.verdict}">${a.verdict}</span>` : `<span class="pill NONE">not assessed</span>`;
}

function timelockText(p) {
  if (p.state !== "QUEUED") return p.state === "ACTIVE" ? `voting ends ${ts(p.voting_ends)}` : "—";
  const left = Number(p.eta) - now;
  return left > 0 ? `${Math.floor(left / 60)}m ${left % 60}s until eta` : `eta passed (${ts(p.eta)})`;
}

function renderProposals() {
  $("proposals").innerHTML = proposals.length ? proposals.map((p) => {
    const dec = decodeAction(p.target, p.calldata);
    const turnout = Number(p.for_votes) + Number(p.against_votes);
    const pct = p.total_power > 0 ? (100 * turnout / Number(p.total_power)).toFixed(1) : "0";
    return `<tr class="row" data-pid="${p.id}"><td>${p.id}</td><td>${esc(p.description)}</td><td>${esc(dec.text)}</td>
      <td>${pct}% / ${(Number(p.quorum_bps) / 100).toFixed(1)}%</td><td class="state-${p.state}">${p.state}</td>
      <td>${timelockText(p)}</td><td>${verdictPill(Number(p.id))}</td></tr>`;
  }).join("") : `<tr><td colspan="7" class="muted">no proposals yet</td></tr>`;
  for (const tr of $("proposals").querySelectorAll("tr.row")) tr.onclick = () => renderDetail(Number(tr.dataset.pid));
}

function renderDetail(pid) {
  const p = proposals.find((x) => Number(x.id) === pid); if (!p) return;
  const a = byProposal.get(pid);
  const dec = decodeAction(p.target, p.calldata);
  const mismatch = a ? !a.description_matches_calldata : null;
  const cls = mismatch === null ? "" : mismatch ? "mismatch" : "match";
  const banner = !a ? `<div class="banner dim">Circuit has not assessed this proposal yet.</div>`
    : a.verdict === "VETO" ? `<div class="banner bad">VETOED by Circuit — ${esc(a.gate_reason)}. The governor's execute() now reverts.</div>`
    : a.verdict === "FLAG" ? `<div class="banner bad" style="background:#2a230f;color:#f2c94c">FLAG — ${esc(a.gate_reason)}</div>`
    : `<div class="banner ok">NO_ACTION — ${esc(a.gate_reason)}</div>`;
  $("detail").innerHTML = `<h2>Proposal #${pid} — ${p.state}</h2>
    <div class="side">
      <div class="${cls}"><div class="label">what the proposal SAYS</div><div class="says">“${esc(p.description)}”</div></div>
      <div class="${cls}"><div class="label">what the calldata DOES</div><div class="does">${esc(a ? a.action : dec.text)}</div>
        <div class="muted" style="font-size:12px;margin-top:6px">raw: ${esc(p.calldata)}</div></div>
    </div>
    ${banner}
    <div style="margin-top:14px" class="side">
      <div><div class="label">proposal (from ${addrLink(cfg.governor)})</div><dl>
        <dt>proposer</dt><dd>${addrLink(p.proposer)} <span class="muted">(${(Number(p.proposer_power) * 100 / Number(p.total_power || 1)).toFixed(1)}% of power, held since ${ts(p.proposer_power_since)})</span></dd>
        <dt>target</dt><dd>${addrLink(p.target)}</dd>
        <dt>votes</dt><dd>for ${p.for_votes} / against ${p.against_votes} / total power ${p.total_power}</dd>
        <dt>created</dt><dd>${ts(p.created_at)}</dd><dt>voting ends</dt><dd>${ts(p.voting_ends)}</dd><dt>eta</dt><dd>${ts(p.eta)}</dd>
      </dl></div>
      <div><div class="label">assessment (from ${addrLink(cfg.circuit)})</div>${a ? `<dl>
        <dt>verdict</dt><dd><span class="pill ${a.verdict}">${a.verdict}</span> ${a.vetoed ? "— veto message emitted" : ""}</dd>
        <dt>hostile</dt><dd>${a.hostile} (confidence ${a.confidence}/100, high ≥ ${gcfg.high_confidence ?? "?"})</dd>
        <dt>description matches calldata</dt><dd class="${a.description_matches_calldata ? "" : "err"}">${a.description_matches_calldata}</dd>
        <dt>privileged target</dt><dd>${a.privileged} <span class="muted">(interface known: ${a.known_interface}, decodable: ${a.decodable})</span></dd>
        <dt>turnout</dt><dd>${(Number(a.turnout_bps) / 100).toFixed(1)}% <span class="muted">(Circuit floor ${(Number(gcfg.quorum_threshold_bps ?? 0) / 100).toFixed(1)}%)</span></dd>
        <dt>proposer share / age</dt><dd>${(Number(a.proposer_power_bps) / 100).toFixed(1)}% / ${a.proposer_power_age}s</dd>
        <dt>value at risk</dt><dd>${a.value_at_risk}</dd>
        <dt>cited call</dt><dd>${esc(a.cited_call)}</dd>
        <dt>assessed</dt><dd>${ts(a.assessed_at)} by ${addrLink(a.assessed_by)}</dd>
      </dl><div class="label" style="margin-top:8px">model reasoning (stored, not compared by validators)</div><div class="reason">${esc(a.reasoning)}</div>` : `<span class="muted">none</span>`}</div>
    </div>`;
}

function renderLog() {
  $("log").innerHTML = assessments.length ? assessments.slice().reverse().map((a) => `<tr class="row" data-pid="${a.proposal_id}"><td>${a.index}</td><td>#${a.proposal_id}</td>
    <td><span class="pill ${a.verdict}">${a.verdict}</span></td><td>${a.hostile}</td><td class="${a.description_matches_calldata ? "" : "err"}">${a.description_matches_calldata}</td>
    <td>${a.confidence}</td><td>${esc(a.gate_reason)}</td><td>${ts(a.assessed_at)}</td></tr>`).join("")
    : `<tr><td colspan="8" class="muted">no assessments yet</td></tr>`;
  for (const tr of $("log").querySelectorAll("tr.row")) tr.onclick = () => renderDetail(Number(tr.dataset.pid));
}

const gen = (wei) => (Number(BigInt(wei)) / 1e18).toFixed(4) + " GEN";

function renderVault(v) {
  const p = protocol;
  const outflow = p ? Math.max(0, Number(v.total_withdrawals) - Number(p.baseline_withdrawals)) : 0;
  const bps = p && Number(p.baseline_balance) > 0 ? Math.floor(outflow * 10000 / Number(p.baseline_balance)) : 0;
  const last = drains[drains.length - 1];
  $("vault").className = "kv";
  $("vault").innerHTML = [
    ["contract", addrLink(cfg.vault)],
    ["paused", `<b class="${v.paused ? "err" : ""}">${v.paused}</b>`], ["restricted", `<b class="${v.restricted ? "err" : ""}">${v.restricted}</b>`],
    ["balance", gen(v.balance)],
    ["outflow this window", p ? `<b class="${bps >= Number(p.drain_threshold_bps) ? "err" : ""}">${(bps / 100).toFixed(1)}%</b> of ${gen(p.baseline_balance)} <span class="muted">(threshold ${(Number(p.drain_threshold_bps) / 100).toFixed(0)}%, window ${p.window_s}s)</span>` : "—"],
    ["latest verdict", last ? `<span class="pill ${last.verdict}">${last.verdict}</span> <span class="muted">${ts(last.assessed_at)}</span>` : `<span class="pill NONE">none yet</span>`],
    ["owner (governance)", addrLink(v.owner)], ["controller (Circuit)", addrLink(v.controller)],
    ["fee_bps", v.fee_bps], ["pause count", v.pause_count], ["last action", v.last_action],
  ].map(([k, val]) => `<div><span>${k}</span>${val}</div>`).join("");
}

function renderDrains() {
  $("drain").innerHTML = drains.length ? drains.slice().reverse().map((a) => `<tr class="row" data-idx="${a.index}"><td>${a.index}</td>
    <td><span class="pill ${a.verdict}">${a.verdict}</span></td><td class="${a.drain_above_threshold ? "err" : ""}">${(Number(a.outflow_bps) / 100).toFixed(1)}%</td>
    <td>${a.drain_above_threshold ? "above" : "below"}</td><td>${a.corroboration}</td><td class="muted">${a.model_verdict}</td><td>${a.confidence}</td>
    <td>${a.sources_ok}/${a.sources_failed.length}${a.sources_failed.length ? ' <span class="err">failed</span>' : ""}</td><td>${a.action_taken}</td><td>${ts(a.assessed_at)}</td></tr>`).join("")
    : `<tr><td colspan="10" class="muted">no assessments yet</td></tr>`;
  for (const tr of $("drain").querySelectorAll("tr.row")) tr.onclick = () => renderDrainDetail(Number(tr.dataset.idx));
}

function renderDrainDetail(idx) {
  const a = drains.find((x) => Number(x.index) === idx); if (!a) return;
  const cls = a.verdict === "NO_ACTION" ? "ok" : a.verdict === "PAUSE" ? "bad" : "dim";
  $("drain-detail").innerHTML = `<div class="banner ${cls}"><b>#${idx} ${a.verdict}</b> — ${esc(a.gate_reason)} · action: ${a.action_taken}${a.bond_slashed > 0 ? " · bond slashed " + gen(a.bond_slashed) : ""}</div>
    <div class="side" style="margin-top:10px">
      <div><div class="label">MEASURED on-chain (authoritative)</div><dl>
        <dt>balance now</dt><dd>${gen(a.balance)}</dd><dt>balance at window start</dt><dd>${gen(a.baseline_balance)}</dd>
        <dt>withdrawn since window start</dt><dd>${gen(a.outflow)} (${(Number(a.outflow_bps) / 100).toFixed(1)}%)</dd>
        <dt>drain above threshold</dt><dd class="${a.drain_above_threshold ? "err" : ""}">${a.drain_above_threshold}</dd>
        <dt>already paused</dt><dd>${a.already_paused}</dd>
        <dt>assessed</dt><dd>${ts(a.assessed_at)} by ${addrLink(a.caller)}</dd></dl></div>
      <div><div class="label">JUDGED by the committee</div><dl>
        <dt>model verdict</dt><dd>${a.model_verdict} <span class="muted">(gate decided: ${a.verdict})</span></dd>
        <dt>corroboration</dt><dd>${a.corroboration}</dd><dt>confidence</dt><dd>${a.confidence}/100 (high ≥ ${gcfg.high_confidence ?? "?"})</dd>
        <dt>cited</dt><dd>${esc(a.cited)}</dd></dl>
        <div class="label" style="margin-top:8px">reasoning (stored, not compared by validators)</div><div class="reason">${esc(a.reasoning)}</div></div>
    </div>
    <div class="label" style="margin-top:12px">EVIDENCE — exactly what the leader fetched (${a.sources_ok} ok, ${a.sources_failed.length} failed; failures shown, never hidden)</div>
    <table><thead><tr><th>source</th><th>status</th><th>category</th><th>excerpt / error</th></tr></thead><tbody>
      ${a.web_evidence.map((e) => `<tr class="${e.category === "SOURCE_FAILED" ? "err" : ""}"><td><a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.url)}</a></td><td>${e.status}</td><td>${e.category}</td><td>${esc(e.excerpt || e.error || "")}</td></tr>`).join("")}
    </tbody></table>`;
}

async function refresh() {
  try {
    const [vault, ps, as, cc, gc, ds, pr] = await Promise.all([
      read(cfg.vault, "get_state"), read(cfg.governor, "get_proposals"), read(cfg.circuit, "get_assessments"),
      read(cfg.circuit, "get_config"), read(cfg.governor, "get_config"), read(cfg.circuit, "get_drain_assessments"),
      cfg.protocol_id ? read(cfg.circuit, "get_protocol", [cfg.protocol_id]).catch(() => null) : null,
    ]);
    proposals = ps; assessments = as; gcfg = cc; now = Number(gc.now); drains = ds; protocol = pr;
    byProposal = new Map(); for (const a of as) byProposal.set(Number(a.proposal_id), a);
    renderVault(vault); renderDrains(); renderProposals(); renderLog();
    if (!document.querySelector("#drain-detail .banner") && drains.length) renderDrainDetail(Number(drains[drains.length - 1].index));
    $("net").textContent = `${cfg.network} · governor ${short(cfg.governor)} · circuit ${short(cfg.circuit)}`;
    $("updated").textContent = `updated ${new Date().toISOString().slice(11, 19)} UTC`;
    const sel = document.querySelector("#detail h2")?.textContent.match(/#(\d+)/);
    if (sel) renderDetail(Number(sel[1])); else if (proposals.length) renderDetail(Number(proposals[proposals.length - 1].id));
  } catch (e) {
    $("net").innerHTML = `<span class="err">read failed: ${esc(e.shortMessage || e.message)}</span>`;
    console.error(e);
  }
}
await refresh();
setInterval(refresh, 20000);
