# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

# Verification probe for Addendum A §A2.7. Every method here answers one
# "verify before building" question about the GenVM sandbox on Studio Next.

import genlayer as gl
from genlayer.types import *


class GovProbe(gl.contract.Contract):
    emitted: u256

    def __init__(self):
        self.emitted = 0

    # A2.7 #1 — what is importable inside the sandbox?
    @gl.public.view
    def env(self) -> dict:
        out = {}
        for name in ["genlayer.calldata", "genlayer.evm.calldata", "hashlib", "json",
                     "eth_abi", "eth_utils", "web3", "base64", "re", "datetime"]:
            try:
                __import__(name)
                out[name] = True
            except Exception as e:
                out[name] = "ERR " + type(e).__name__
        try:
            from genlayer.types.keccak import Keccak256
            out["keccak_pause"] = Keccak256(b"pause()").digest()[:4].hex()
        except Exception as e:
            out["keccak_pause"] = "ERR " + type(e).__name__
        return out

    # A2.7 #2 — read another Intelligent Contract's state.
    @gl.public.view
    def read_vault(self, vault: str) -> dict:
        return gl.contract.get_at(Address(vault)).view().get_state()

    # A2.7 #1/#3 — bytes argument round trip + GenVM calldata decode in-VM,
    # returning a decode-friendly shape.
    @gl.public.view
    def decode_calldata(self, data: bytes) -> dict:
        import genlayer.calldata as cd
        try:
            d = cd.decode(data)
        except Exception as e:
            return {"ok": False, "error": type(e).__name__ + ": " + str(e), "raw_len": len(data)}
        method = d.get("", None) if isinstance(d, dict) else None
        args = d.get("args", []) if isinstance(d, dict) else []
        return {
            "ok": True,
            "method": method,
            "args": [str(a) if isinstance(a, Address) else a for a in args],
            "types": [type(a).__name__ for a in args],
            "human": cd.to_str(d),
        }

    # A2.7 #3 — struct/array return shapes.
    @gl.public.view
    def shapes(self) -> dict:
        return {
            "targets": [str(Address("0x" + "11" * 20)), str(Address("0x" + "22" * 20))],
            "calldatas": [b"\x0e\x00\x2cpause", b""],
            "rows": [{"id": 1, "ok": True}, {"id": 2, "ok": False}],
            "big": 2**200,
        }

    # A2.7 #4 — one contract emitting messages to two targets in one tx.
    @gl.public.write
    def emit_two(self, a: str, b: str) -> None:
        gl.contract.get_at(Address(a)).emit(on="finalized").pause()
        gl.contract.get_at(Address(b)).emit(on="finalized").pause()
        self.emitted = self.emitted + 2

    @gl.public.view
    def get_state(self) -> dict:
        return {"emitted": int(self.emitted)}

    # A4 step 5 — veto issued from a contract address, as Circuit will.
    @gl.public.write
    def emit_veto(self, governor: str, proposal_id: u256) -> None:
        gl.contract.get_at(Address(governor)).emit(on="finalized").veto(proposal_id)
        self.emitted = self.emitted + 1
