# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

# Spike 3: can an Intelligent Contract on Studio Next talk to an EVM contract?

import genlayer as gl
from genlayer.types import *


@gl.evm.contract_interface
class IPausable:
    class View:
        def paused(self) -> bool: ...

    class Write:
        def pause(self) -> None: ...


class EvmProbe(gl.contract.Contract):
    last: str

    def __init__(self):
        self.last = ""

    @gl.public.write
    def view_paused(self, target: str) -> None:
        r = IPausable(Address(target)).view().paused()
        self.last = f"view ok: {r!r}"

    @gl.public.write
    def emit_pause(self, target: str) -> None:
        IPausable(Address(target)).emit().pause()
        self.last = "emit ok"

    @gl.public.view
    def get(self) -> str:
        return self.last
