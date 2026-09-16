# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

# Spikes 1 and 2 for the drain path's GATHER step, on real uncontrolled content:
#   - does a heterogeneous committee agree on closed fields derived from a live
#     page whose bytes differ between fetches?
#   - what happens when a source is down or erroring — does the fetch raise and
#     kill the transaction, or can it be recorded as failed and execution continue?
#   - what does a multi-fetch non-deterministic transaction cost in latency?

import genlayer as gl
from genlayer.types import *

CATEGORIES = ("NO_CLAIM", "EXPLOIT_CLAIM", "PAUSE_CLAIM", "UNRELATED", "SOURCE_FAILED")


@gl.storage.allow
class Run:
    url: str
    keyword: str
    status: u256
    body_len: u256
    keyword_hit: bool
    category: str
    error: str
    excerpt: str


def fetch_and_classify(url: str, keyword: str, max_chars: int) -> dict:
    """One source. Never raises for a bad source: a failure is data."""
    try:
        res = gl.nondet.web.get(url)
        status = int(getattr(res, "status", getattr(res, "status_code", 0)))
        body = res.body.decode("utf-8", errors="replace")
    except Exception as e:  # unreachable host, timeout, VM-level refusal
        return {"status": 0, "full_len": 0, "hit": False, "category": "SOURCE_FAILED",
                "error": (type(e).__name__ + ": " + str(e))[:200], "excerpt": "", "digest": ""}
    full_len = len(body)
    if status >= 400:
        return {"status": status, "full_len": full_len, "hit": False, "category": "SOURCE_FAILED",
                "error": "http " + str(status), "excerpt": body[:200], "digest": ""}
    body = body[:max_chars]
    hit = keyword.lower() in body.lower()
    out = gl.nondet.exec_prompt(
        "You are reading a security news source for claims about the DeFi protocol "
        f"named '{keyword}'. Classify the text into exactly one category:\n"
        "NO_CLAIM = the protocol is mentioned but there is no exploit/drain/hack claim about it; "
        "EXPLOIT_CLAIM = the text claims it is being or was exploited, drained or hacked; "
        "PAUSE_CLAIM = the text says it has been paused or halted; "
        "UNRELATED = the protocol is not mentioned at all.\n"
        'Answer with JSON only: {"category": "<one of the four>"}\n\nTEXT:\n' + body,
        response_format="json",
    )
    cat = str(out.get("category", "")).strip().upper() if isinstance(out, dict) else ""
    if cat not in CATEGORIES or cat == "SOURCE_FAILED":
        raise gl.vm.UserError("[LLM_ERROR] category outside enum: " + cat)
    import hashlib
    return {"status": status, "full_len": full_len, "hit": hit, "category": cat, "error": "",
            "excerpt": body[:200], "digest": hashlib.sha256(body.encode()).hexdigest()[:12]}


def same_closed_fields(l: dict, m: dict) -> bool:
    # Status class, keyword hit and category must agree; bytes and lengths may not.
    return int(l["status"]) // 100 == int(m["status"]) // 100 and bool(l["hit"]) == bool(m["hit"]) and l["category"] == m["category"]


class EvidenceProbe(gl.contract.Contract):
    runs: gl.storage.DynArray[Run]

    def __init__(self):
        pass

    def _record(self, url: str, keyword: str, r: dict) -> None:
        run = self.runs.append_new_get()
        run.url = url
        run.keyword = keyword
        run.status = int(r["status"])
        run.body_len = int(r["full_len"])
        run.keyword_hit = bool(r["hit"])
        run.category = str(r["category"])
        run.error = str(r["error"])
        run.excerpt = str(r["excerpt"])

    @gl.public.write
    def probe(self, url: str, keyword: str, max_chars: u256) -> str:
        def leader_fn():
            return fetch_and_classify(url, keyword, int(max_chars))

        def validator_fn(leader: gl.vm.Result) -> bool:
            if not isinstance(leader, gl.vm.Return):
                return False
            l = leader.calldata
            mine = leader_fn()
            ok = same_closed_fields(l, mine)
            print(f"validator: leader status={l['status']} len={l['full_len']} sha={l.get('digest')} hit={l['hit']} cat={l['category']} | "
                  f"mine status={mine['status']} len={mine['full_len']} sha={mine.get('digest')} hit={mine['hit']} cat={mine['category']} -> {ok}")
            return ok

        r = gl.vm.run_nondet_default(leader_fn, validator_fn)
        self._record(url, keyword, r)
        return r["category"]

    @gl.public.write
    def probe_many(self, urls: list, keyword: str, max_chars: u256) -> list:
        def leader_fn():
            return [fetch_and_classify(str(u), keyword, int(max_chars)) for u in urls]

        def validator_fn(leader: gl.vm.Result) -> bool:
            if not isinstance(leader, gl.vm.Return):
                return False
            l = leader.calldata
            mine = leader_fn()
            if len(l) != len(mine):
                return False
            oks = [same_closed_fields(a, b) for a, b in zip(l, mine)]
            print("validator per-source:", [(a["category"], a.get("digest"), b["category"], b.get("digest"), o) for a, b, o in zip(l, mine, oks)])
            return all(oks)

        rs = gl.vm.run_nondet_default(leader_fn, validator_fn)
        for u, r in zip(urls, rs):
            self._record(str(u), keyword, r)
        return [r["category"] for r in rs]

    @gl.public.view
    def get_runs(self) -> list:
        return [{"url": x.url, "keyword": x.keyword, "status": int(x.status), "body_len": int(x.body_len),
                 "keyword_hit": x.keyword_hit, "category": x.category, "error": x.error, "excerpt": x.excerpt} for x in self.runs]
