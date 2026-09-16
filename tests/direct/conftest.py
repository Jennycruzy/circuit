"""Multi-contract harness for gltest direct mode.

The direct VM does not itself route cross-contract calls, internal messages, or
events; it exposes ``_gl_call_hook`` for that. This harness keeps a registry of
locally deployed contracts, answers ``CallContract`` views from it, records
``EmitInternalMessage`` / ``EmitEvent``, and can *deliver* recorded messages so
a governor → vault action can be exercised end to end.
"""
from __future__ import annotations

import pytest


def as_bytes(addr) -> bytes:
    if isinstance(addr, bytes):
        return addr
    if hasattr(addr, "as_bytes"):
        return addr.as_bytes
    return bytes.fromhex(str(addr).removeprefix("0x"))


def address_text(addr) -> str:
    """Checksummed, matching ``str(Address)`` inside contracts."""
    try:
        from genlayer.types import Address
        return str(Address(as_bytes(addr)))
    except ImportError:  # SDK not on sys.path until the first deploy
        return "0x" + as_bytes(addr).hex()


def sync_message(vm) -> None:
    """direct_vm refreshes sender/value only; contracts also read the
    transaction datetime and their own address from ``gl.message``."""
    vm._refresh_gl_message()
    try:
        import genlayer.message as gm
        from genlayer.types import Address
    except ImportError:
        return
    addr = Address(bytes(vm._contract_address))
    gm.contract_address = addr
    if isinstance(getattr(gm, "raw", None), dict):
        gm.raw["contract_address"] = addr
        gm.raw["datetime"] = vm._datetime


class Handle:
    """A deployed contract; every call runs with ``contract_address`` and the
    contract's own storage manager installed (direct mode has one global
    slot store, so two contracts would otherwise overlay each other)."""

    def __init__(self, chain: "Chain", proxy, addr: bytes, storage):
        self.chain, self.proxy, self.addr, self.storage = chain, proxy, addr, storage

    @property
    def address(self) -> str:
        return address_text(self.addr)

    def __getattr__(self, name):
        target = getattr(self.proxy, name)
        if not callable(target):
            return target

        def call(*args, **kwargs):
            vm = self.chain.vm
            prev, prev_storage = vm._contract_address, vm._storage
            vm._contract_address, vm._storage = self.addr, self.storage
            sync_message(vm)
            try:
                return target(*args, **kwargs)
            finally:
                vm._contract_address, vm._storage = prev, prev_storage
                sync_message(vm)

        return call


class Chain:
    def __init__(self, vm):
        self.vm = vm
        self.contracts: dict[bytes, Handle] = {}
        self.messages: list[dict] = []
        self.events: list[dict] = []
        vm._gl_call_hook = self.hook

    def deploy(self, direct_deploy, path, *args) -> Handle:
        # The SDK registers a single main contract per process; direct mode
        # allocates by explicit class, so the guard can be cleared per deploy.
        # (The SDK only lands on sys.path during the first deploy.)
        try:
            import genlayer.contract as glc
            glc.__known_contract__ = None
        except ImportError:
            pass
        from gltest.direct.vm import InmemManager
        storage = InmemManager()
        self.vm._storage = storage
        proxy = direct_deploy(str(path), *args)
        h = Handle(self, proxy, bytes(self.vm._contract_address), storage)
        self.contracts[h.addr] = h
        return h

    # -- gl_call routing ----------------------------------------------------
    def hook(self, vm, request):
        from genlayer import calldata

        if "EmitInternalMessage" in request:
            m = dict(request["EmitInternalMessage"])
            m["from"] = bytes(vm._contract_address)
            self.messages.append(m)
            return {"ok": None}
        if "EmitEvent" in request:
            self.events.append(request["EmitEvent"])
            return {"ok": None}
        if "CallContract" in request:
            req = request["CallContract"]
            h = self.contracts.get(as_bytes(req["address"]))
            if h is None:
                return bytes([2]) + b"no contract at address"
            cd = req["calldata"]
            try:
                result = getattr(h, cd[""])(*cd.get("args", []), **cd.get("kwargs", {}))
            except Exception as e:  # UserError → USER_ERROR result
                data = getattr(e, "data", str(e))
                return bytes([1]) + calldata.encode(data)
            return bytes([0]) + calldata.encode(result)
        return None

    # -- helpers ----------------------------------------------------------------
    def deliver(self) -> list[dict]:
        """Apply every recorded message to its target, as the network would on
        finality. The message sender is the emitting contract."""
        delivered, pending = [], self.messages
        self.messages = []
        for m in pending:
            h = self.contracts[as_bytes(m["address"])]
            cd = m["calldata"]
            prev_sender, prev_value = self.vm.sender, self.vm.value
            self.vm.sender = m["from"]
            self.vm.value = int(m.get("value", 0))
            try:
                getattr(h, cd[""])(*cd.get("args", []), **cd.get("kwargs", {}))
            finally:
                self.vm.sender, self.vm.value = prev_sender, prev_value
            delivered.append(m)
        return delivered

    def events_named(self, signature: str) -> list[dict]:
        """Events whose first topic is keccak(signature), e.g. ``Vetoed(proposal_id)``."""
        from genlayer.types.keccak import Keccak256

        topic = Keccak256(signature.encode()).digest()
        return [e["blob"] for e in self.events if bytes(e["topics"][0]) == topic]


@pytest.fixture
def chain(direct_vm):
    return Chain(direct_vm)
