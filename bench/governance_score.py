#!/usr/bin/env python3
"""Report measured outcomes from the live subset of governance_corpus.json.

Offline fixtures are intentionally excluded. Add a result object and status=live
only after a case has actually been assessed on-chain.
"""
import json
from pathlib import Path

entries = json.loads((Path(__file__).parent / "governance_corpus.json").read_text())["entries"]
live = [e for e in entries if e.get("status") == "live" and e.get("result")]
benign = [e for e in live if e.get("kind") == "benign"]
hostile = [e for e in live if e.get("kind") == "hostile"]
false_veto = [e for e in benign if e["result"].get("verdict") == "VETO"]
missed = [e for e in hostile if e["result"].get("verdict") not in {"VETO", "FLAG"}]
fixtures = [e for e in entries if e.get("status") == "fixture"]
rate = f"{len(false_veto)}/{len(benign)} ({100 * len(false_veto) / len(benign):.1f}%)" if benign else "n/a"
print(f"live assessed: {len(live)}")
print(f"live benign: {len(benign)} | false veto: {len(false_veto)} | false-veto rate: {rate}")
print(f"live hostile: {len(hostile)} | missed: {len(missed)}")
print(f"offline fixtures excluded: {len(fixtures)}")
