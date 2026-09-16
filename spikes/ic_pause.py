# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

import genlayer as gl
from genlayer.types import *


class InternalPauseProbe(gl.contract.Contract):
    target: Address
    emitted: bool

    def __init__(self, target: str):
        self.target = Address(target)
        self.emitted = False

    @gl.public.write
    def emit_pause(self) -> None:
        target = gl.get_contract_at(self.target)
        target.emit(on="finalized").pause()
        self.emitted = True

    @gl.public.view
    def get_state(self) -> dict:
        return {
            "target": str(self.target),
            "emitted": self.emitted,
        }
