# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

# DemoVault — the protocol Circuit protects. Two authorities:
#   controller : Circuit. May pause(). Bound once.
#   owner      : governance (DemoGovernor). May change parameters, transfer
#                ownership, or sweep funds — the privileged surface a hostile
#                proposal would target.

import genlayer as gl
from genlayer.types import *


ZERO_ADDRESS = Address("0x0000000000000000000000000000000000000000")

# Methods a hostile proposal could abuse; Circuit's DECODE step reads this list.
PRIVILEGED = ["set_owner", "set_fee_bps", "sweep", "pause", "restrict"]


@gl.evm.contract_interface
class Recipient:
    class View:
        pass

    class Write:
        pass


class OwnerChanged(gl.chain.Event):
    def __init__(self, new_owner: Address, /, **blob): ...


class FeeChanged(gl.chain.Event):
    def __init__(self, /, **blob): ...


class Swept(gl.chain.Event):
    def __init__(self, recipient: Address, /, **blob): ...


class Paused(gl.chain.Event):
    def __init__(self, controller: Address, /, **blob): ...


class Restricted(gl.chain.Event):
    def __init__(self, controller: Address, /, **blob): ...


class DemoVault(gl.contract.Contract):
    controller: Address
    initializer: Address
    owner: Address
    paused: bool
    restricted: bool      # deposits blocked, withdrawals still allowed (RESTRICT tier)
    fee_bps: u256
    total_deposits: u256
    total_withdrawals: u256
    pause_count: u256
    last_action: str

    def __init__(self, initializer: str):
        self.controller = ZERO_ADDRESS
        self.initializer = Address(initializer)
        self.owner = Address(initializer)
        self.paused = False
        self.restricted = False
        self.fee_bps = 0
        self.total_deposits = 0
        self.total_withdrawals = 0
        self.pause_count = 0
        self.last_action = "created"

    # ---- one-time Circuit binding -------------------------------------
    @gl.public.write
    def set_controller(self, controller: str) -> None:
        if gl.message.sender_address != self.initializer:
            raise gl.vm.UserError("only the initializer may bind the controller")
        if self.controller != ZERO_ADDRESS:
            raise gl.vm.UserError("controller already bound")

        next_controller = Address(controller)
        if next_controller == ZERO_ADDRESS:
            raise gl.vm.UserError("controller cannot be zero")
        self.controller = next_controller
        self.initializer = ZERO_ADDRESS
        self.last_action = "controller_bound"

    # ---- user surface ---------------------------------------------------
    @gl.public.write.payable
    def deposit(self) -> None:
        if self.paused:
            raise gl.vm.UserError("vault is paused")
        if self.restricted:
            raise gl.vm.UserError("deposits are restricted")

        amount = gl.message.value
        if amount <= 0:
            raise gl.vm.UserError("deposit value must be positive")
        self.total_deposits = self.total_deposits + amount
        self.last_action = "deposit"

    @gl.public.write
    def withdraw(self, amount: u256, recipient: str) -> None:
        if self.paused:
            raise gl.vm.UserError("vault is paused")
        if amount <= 0:
            raise gl.vm.UserError("withdrawal value must be positive")
        if amount > self.balance:
            raise gl.vm.UserError("insufficient vault balance")

        Recipient(Address(recipient)).emit_transfer(value=amount)
        self.total_withdrawals = self.total_withdrawals + amount
        self.last_action = "withdraw"

    # ---- Circuit surface ------------------------------------------------
    @gl.public.write
    def pause(self) -> None:
        if gl.message.sender_address != self.controller:
            raise gl.vm.UserError("only the bound controller may pause")
        if self.paused:
            return
        self.paused = True
        self.restricted = True
        self.pause_count = self.pause_count + 1
        self.last_action = "paused"
        Paused(self.controller).emit()

    @gl.public.write
    def restrict(self) -> None:
        if gl.message.sender_address != self.controller:
            raise gl.vm.UserError("only the bound controller may restrict")
        if self.restricted:
            return
        self.restricted = True
        self.last_action = "restricted"
        Restricted(self.controller).emit()

    # ---- governance surface (owner = DemoGovernor) ----------------------
    def _only_owner(self) -> None:
        if gl.message.sender_address != self.owner:
            raise gl.vm.UserError("only the owner may call this")

    @gl.public.write
    def set_owner(self, new_owner: str) -> None:
        self._only_owner()
        nxt = Address(new_owner)
        if nxt == ZERO_ADDRESS:
            raise gl.vm.UserError("owner cannot be zero")
        self.owner = nxt
        self.last_action = "owner_changed"
        OwnerChanged(nxt).emit()

    @gl.public.write
    def set_fee_bps(self, bps: u256) -> None:
        self._only_owner()
        if bps > 10_000:
            raise gl.vm.UserError("fee above 100%")
        self.fee_bps = bps
        self.last_action = "fee_changed"
        FeeChanged(bps=bps).emit()

    @gl.public.write
    def sweep(self, recipient: str) -> None:
        self._only_owner()
        amount = self.balance
        if amount <= 0:
            raise gl.vm.UserError("nothing to sweep")
        Recipient(Address(recipient)).emit_transfer(value=amount)
        self.total_withdrawals = self.total_withdrawals + amount
        self.last_action = "swept"
        Swept(Address(recipient), amount=amount).emit()

    # ---- reads ----------------------------------------------------------
    @gl.public.view
    def privileged_methods(self) -> list:
        return PRIVILEGED

    @gl.public.view
    def get_state(self) -> dict:
        return {
            "controller": str(self.controller),
            "owner": str(self.owner),
            "paused": self.paused,
            "restricted": self.restricted,
            "fee_bps": int(self.fee_bps),
            "balance": int(self.balance),
            "total_deposits": int(self.total_deposits),
            "total_withdrawals": int(self.total_withdrawals),
            "pause_count": int(self.pause_count),
            "last_action": self.last_action,
        }
