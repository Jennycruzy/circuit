# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

import genlayer as gl
from genlayer.types import *


ZERO_ADDRESS = Address("0x0000000000000000000000000000000000000000")


@gl.evm.contract_interface
class Recipient:
    class View:
        pass

    class Write:
        pass


class DemoVault(gl.contract.Contract):
    controller: Address
    initializer: Address
    paused: bool
    total_deposits: u256
    total_withdrawals: u256
    pause_count: u256
    last_action: str

    def __init__(self, initializer: str):
        self.controller = ZERO_ADDRESS
        self.initializer = Address(initializer)
        self.paused = False
        self.total_deposits = 0
        self.total_withdrawals = 0
        self.pause_count = 0
        self.last_action = "created"

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

    @gl.public.write.payable
    def deposit(self) -> None:
        if self.paused:
            raise gl.vm.UserError("vault is paused")

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

    @gl.public.write
    def pause(self) -> None:
        if gl.message.sender_address != self.controller:
            raise gl.vm.UserError("only the bound controller may pause")
        if self.paused:
            return
        self.paused = True
        self.pause_count = self.pause_count + 1
        self.last_action = "paused"

    @gl.public.view
    def get_state(self) -> dict:
        return {
            "controller": str(self.controller),
            "paused": self.paused,
            "balance": int(self.balance),
            "total_deposits": int(self.total_deposits),
            "total_withdrawals": int(self.total_withdrawals),
            "pause_count": int(self.pause_count),
            "last_action": self.last_action,
        }
