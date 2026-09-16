# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

# Day-one spike: prove one real non-deterministic transaction (a web fetch and
# an LLM prompt) reaches consensus on the live network and lands in storage.

import json
import genlayer as gl
from genlayer.types import *

ERROR_TRANSIENT = "[TRANSIENT]"
ERROR_LLM = "[LLM_ERROR]"


class Hello(gl.contract.Contract):
    greeting: str
    last_url: str
    last_status: u256
    last_body_len: u256
    last_topic: str
    runs: u256

    def __init__(self):
        self.greeting = "hello"
        self.last_url = ""
        self.last_status = 0
        self.last_body_len = 0
        self.last_topic = ""
        self.runs = 0

    @gl.public.view
    def get(self) -> dict:
        return {
            "greeting": self.greeting,
            "last_url": self.last_url,
            "last_status": int(self.last_status),
            "last_body_len": int(self.last_body_len),
            "last_topic": self.last_topic,
            "runs": int(self.runs),
        }

    @gl.public.write
    def probe(self, url: str) -> None:
        def leader_fn():
            res = gl.nondet.web.get(url)
            status = int(getattr(res, "status", getattr(res, "status_code", 0)))
            if status >= 500:
                raise gl.vm.UserError(f"{ERROR_TRANSIENT} upstream {status}")
            body = res.body.decode("utf-8", errors="replace")[:4000]
            out = gl.nondet.exec_prompt(
                "Classify the web page text below. Answer with JSON only: "
                '{"kind": "<one of: PLACEHOLDER, ERROR, NEWS, DOCS, OTHER>"}\n'
                "PLACEHOLDER = a reserved/example domain page with no real content. "
                "ERROR = an HTTP error or not-found page. NEWS = a news article. "
                "DOCS = technical documentation. OTHER = anything else.\n\n"
                f"PAGE:\n{body}",
                response_format="json",
            )
            if not isinstance(out, dict) or not isinstance(out.get("kind"), str):
                raise gl.vm.UserError(f"{ERROR_LLM} bad shape: {out!r}")
            kind = out["kind"].strip().upper()
            if kind not in ("PLACEHOLDER", "ERROR", "NEWS", "DOCS", "OTHER"):
                raise gl.vm.UserError(f"{ERROR_LLM} label outside enum: {kind}")
            return {"status": status, "body_len": len(body), "topic": kind}

        def validator_fn(leader: gl.vm.Result) -> bool:
            if not isinstance(leader, gl.vm.Return):
                return False
            mine = leader_fn()
            l = leader.calldata
            # HTTP status must agree; the LLM's enum label must agree.
            # Body length may drift between fetches, so it is not compared.
            print(f"validator: leader={l['topic']}/{l['status']} mine={mine['topic']}/{mine['status']}")
            return int(l["status"]) == mine["status"] and l["topic"] == mine["topic"]

        r = gl.vm.run_nondet_default(leader_fn, validator_fn)
        self.last_url = url
        self.last_status = int(r["status"])
        self.last_body_len = int(r["body_len"])
        self.last_topic = str(r["topic"])
        self.runs = self.runs + 1
