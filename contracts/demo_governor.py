# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

# DemoGovernor — a minimal timelocked governor (Addendum A §A2.3), written as an
# Intelligent Contract because Studio Next has no EVM path. A proposal carries a
# target address and the raw GenVM calldata it will send there; the governor
# never interprets the description. Only the bound Circuit address may veto.
#
# Lifecycle: propose → vote → queue (eta = now + timelock) → execute
#            veto() by Circuit at any point before execute kills it for good.

import datetime

import genlayer as gl
from genlayer.types import *


ZERO_ADDRESS = Address("0x0000000000000000000000000000000000000000")

ACTIVE, QUEUED, EXECUTED, VETOED, DEFEATED = 0, 1, 2, 3, 4
STATE_NAMES = ["ACTIVE", "QUEUED", "EXECUTED", "VETOED", "DEFEATED"]


def _now() -> int:
    # Transaction datetime is identical for leader and every validator.
    raw = gl.message.raw["datetime"].replace("Z", "+00:00")
    return int(datetime.datetime.fromisoformat(raw).timestamp())


@gl.storage.allow
class Proposal:
    proposer: Address
    target: Address
    calldata: bytes
    value: u256
    description: str
    created_at: u256
    voting_ends: u256
    eta: u256
    for_votes: u256
    against_votes: u256
    state: u256


class Proposed(gl.chain.Event):
    def __init__(self, proposal_id: u256, proposer: Address, /, **blob): ...


class Voted(gl.chain.Event):
    def __init__(self, proposal_id: u256, voter: Address, /, **blob): ...


class Queued(gl.chain.Event):
    def __init__(self, proposal_id: u256, /, **blob): ...


class Vetoed(gl.chain.Event):
    def __init__(self, proposal_id: u256, /, **blob): ...


class Executed(gl.chain.Event):
    def __init__(self, proposal_id: u256, /, **blob): ...


class Defeated(gl.chain.Event):
    def __init__(self, proposal_id: u256, /, **blob): ...


class DemoGovernor(gl.contract.Contract):
    deployer: Address
    circuit: Address
    voting_period: u256   # seconds
    timelock: u256        # seconds
    quorum_bps: u256      # of total voting power
    total_power: u256
    power: gl.storage.TreeMap[Address, u256]
    power_since: gl.storage.TreeMap[Address, u256]
    proposals: gl.storage.DynArray[Proposal]
    voted: gl.storage.TreeMap[str, bool]   # f"{id}:{voter}"

    def __init__(self, voting_period: u256, timelock: u256, quorum_bps: u256):
        if quorum_bps > 10_000:
            raise gl.vm.UserError("quorum above 100%")
        self.deployer = gl.message.sender_address
        self.circuit = ZERO_ADDRESS
        self.voting_period = voting_period
        self.timelock = timelock
        self.quorum_bps = quorum_bps
        self.total_power = 0

    # ---- setup ----------------------------------------------------------
    @gl.public.write
    def set_circuit(self, circuit: str) -> None:
        if gl.message.sender_address != self.deployer:
            raise gl.vm.UserError("only the deployer may bind circuit")
        if self.circuit != ZERO_ADDRESS:
            raise gl.vm.UserError("circuit already bound")
        nxt = Address(circuit)
        if nxt == ZERO_ADDRESS:
            raise gl.vm.UserError("circuit cannot be zero")
        self.circuit = nxt

    @gl.public.write
    def grant_power(self, holder: str, amount: u256) -> None:
        # Stands in for a governance token distribution.
        if gl.message.sender_address != self.deployer:
            raise gl.vm.UserError("only the deployer may grant power")
        if amount <= 0:
            raise gl.vm.UserError("amount must be positive")
        h = Address(holder)
        if h not in self.power_since:
            self.power_since[h] = _now()
        self.power[h] = self.power.get(h, 0) + amount
        self.total_power = self.total_power + amount

    # ---- lifecycle ------------------------------------------------------
    @gl.public.write
    def propose(self, target: str, calldata: bytes, value: u256, description: str) -> u256:
        sender = gl.message.sender_address
        if self.power.get(sender, 0) <= 0:
            raise gl.vm.UserError("proposer holds no voting power")
        if len(calldata) == 0:
            raise gl.vm.UserError("calldata required")
        now = _now()
        pid = len(self.proposals)
        p = self.proposals.append_new_get()
        p.proposer = sender
        p.target = Address(target)
        p.calldata = calldata
        p.value = value
        p.description = description
        p.created_at = now
        p.voting_ends = now + self.voting_period
        p.eta = 0
        p.for_votes = 0
        p.against_votes = 0
        p.state = ACTIVE
        Proposed(pid, sender, target=Address(target), description=description).emit()
        return pid

    @gl.public.write
    def vote(self, proposal_id: u256, support: bool) -> None:
        p = self._get(proposal_id)
        if p.state != ACTIVE:
            raise gl.vm.UserError("proposal not active")
        if _now() >= p.voting_ends:
            raise gl.vm.UserError("voting closed")
        voter = gl.message.sender_address
        weight = self.power.get(voter, 0)
        if weight <= 0:
            raise gl.vm.UserError("no voting power")
        key = str(proposal_id) + ":" + str(voter)
        if key in self.voted:
            raise gl.vm.UserError("already voted")
        self.voted[key] = True
        if support:
            p.for_votes = p.for_votes + weight
        else:
            p.against_votes = p.against_votes + weight
        Voted(proposal_id, voter, support=support, weight=weight).emit()

    @gl.public.write
    def queue(self, proposal_id: u256) -> None:
        p = self._get(proposal_id)
        if p.state != ACTIVE:
            raise gl.vm.UserError("proposal not active")
        now = _now()
        if now < p.voting_ends:
            raise gl.vm.UserError("voting still open")
        turnout = p.for_votes + p.against_votes
        passed = p.for_votes > p.against_votes and turnout * 10_000 >= self.quorum_bps * self.total_power
        if not passed:
            p.state = DEFEATED
            Defeated(proposal_id).emit()
            return
        p.eta = now + self.timelock
        p.state = QUEUED
        Queued(proposal_id, eta=p.eta).emit()

    @gl.public.write
    def veto(self, proposal_id: u256) -> None:
        if self.circuit == ZERO_ADDRESS or gl.message.sender_address != self.circuit:
            raise gl.vm.UserError("only circuit may veto")
        p = self._get(proposal_id)
        if p.state not in (ACTIVE, QUEUED):
            raise gl.vm.UserError("proposal cannot be vetoed in its current state")
        p.state = VETOED
        Vetoed(proposal_id).emit()

    @gl.public.write
    def execute(self, proposal_id: u256) -> None:
        p = self._get(proposal_id)
        if p.state == VETOED:
            raise gl.vm.UserError("proposal was vetoed")
        if p.state != QUEUED:
            raise gl.vm.UserError("proposal not queued")
        if _now() < p.eta:
            raise gl.vm.UserError("timelock not elapsed")
        import genlayer.calldata as cd
        decoded = cd.decode(p.calldata)
        if not isinstance(decoded, dict) or not isinstance(decoded.get(""), str):
            raise gl.vm.UserError("calldata does not name a method")
        method = decoded[""]
        args = decoded.get("args", [])
        target = gl.contract.get_at(p.target)
        getattr(target.emit(value=p.value, on="finalized"), method)(*args)
        p.state = EXECUTED
        Executed(proposal_id, target=p.target, method=method).emit()

    # ---- reads ----------------------------------------------------------
    def _get(self, proposal_id: int) -> Proposal:
        if proposal_id >= len(self.proposals):
            raise gl.vm.UserError("unknown proposal")
        return self.proposals[proposal_id]

    def _dump(self, pid: int) -> dict:
        p = self.proposals[pid]
        return {
            "id": pid,
            "proposer": str(p.proposer),
            "target": str(p.target),
            "calldata": p.calldata,
            "value": int(p.value),
            "description": p.description,
            "created_at": int(p.created_at),
            "voting_ends": int(p.voting_ends),
            "eta": int(p.eta),
            "for_votes": int(p.for_votes),
            "against_votes": int(p.against_votes),
            "state": STATE_NAMES[int(p.state)],
            "proposer_power": int(self.power.get(p.proposer, 0)),
            "proposer_power_since": int(self.power_since.get(p.proposer, 0)),
            "total_power": int(self.total_power),
            "quorum_bps": int(self.quorum_bps),
        }

    @gl.public.view
    def get_proposal(self, proposal_id: u256) -> dict:
        self._get(proposal_id)
        return self._dump(proposal_id)

    @gl.public.view
    def get_proposals(self) -> list:
        return [self._dump(i) for i in range(len(self.proposals))]

    @gl.public.view
    def voting_power(self, holder: str) -> dict:
        h = Address(holder)
        return {"power": int(self.power.get(h, 0)), "since": int(self.power_since.get(h, 0))}

    @gl.public.view
    def get_config(self) -> dict:
        return {
            "deployer": str(self.deployer),
            "circuit": str(self.circuit),
            "voting_period": int(self.voting_period),
            "timelock": int(self.timelock),
            "quorum_bps": int(self.quorum_bps),
            "total_power": int(self.total_power),
            "proposal_count": len(self.proposals),
            "now": _now(),
        }
