#!/usr/bin/env python3
"""Replay benchmark, drain path (main-spec §8 / Addendum §A3).

For each historical case, report the share of at-risk funds already gone at
the mark where Circuit's response would land, given a response latency. The
latency is a *measured* number, never a guess: pass what the verification log
records. The result is conservative — the response is placed at the first
published mark at or after the latency, never interpolated earlier.

    python3 bench/replay.py --latency-s 80
"""
import argparse
import json
import pathlib

HERE = pathlib.Path(__file__).parent


def mark_for(latency_s: float, marks_min):
    for m in marks_min:
        if latency_s <= m * 60:
            return m
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latency-s", type=float, required=True,
                    help="measured trigger→pause latency in seconds (see docs/verification.md)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    data = json.loads((HERE / "drain_cases.json").read_text())
    marks = data["marks_min"]
    mark = mark_for(a.latency_s, marks)
    rows = []
    for c in data["cases"]:
        if mark is None:
            gone = None
        else:
            gone = c["drained_usd_at"][marks.index(mark)] / c["at_risk_usd"]
        rows.append({
            "protocol": c["protocol"], "date": c["date"], "at_risk_usd": c["at_risk_usd"],
            "response_mark_min": mark, "gone_pct_at_response": None if gone is None else round(100 * gone, 1),
            "still_on_contract_usd": None if gone is None else round(c["at_risk_usd"] * (1 - gone)),
            "winnable": None if gone is None else gone < 0.5,
            "pause": c["pause"],
            "note": c.get("note", ""),
        })
    if a.json:
        print(json.dumps({"latency_s": a.latency_s, "response_mark_min": mark, "rows": rows}, indent=2))
        return
    print(f"Circuit response latency {a.latency_s:.0f} s → placed at the {mark}-minute mark (conservative)\n")
    print(f"{'protocol':28} {'at risk':>12} {'gone %':>7} {'still there':>13}  verdict     pause surface")
    for r in rows:
        v = "—" if r["winnable"] is None else ("winnable" if r["winnable"] else "TOO LATE")
        print(f"{r['protocol']:28} {r['at_risk_usd']:>12,} {r['gone_pct_at_response']:>7} {r['still_on_contract_usd']:>13,}  {v:9}  {r['pause']}{'  (' + r['note'] + ')' if r['note'] else ''}")
    w = [r for r in rows if r["winnable"]]
    print(f"\n{len(w)}/{len(rows)} cases still had a majority of at-risk funds on the contract at the {mark}-minute mark.")
    print("A detector only helps where a pause surface exists; most of these protocols had none. "
          "Circuit's claim is bounded to pausable targets, and to the three fast drains it would have lost regardless.")
    print("Source: Decurity Research, https://rescue-window.decurity.io (percent of funds at risk).")


if __name__ == "__main__":
    main()
