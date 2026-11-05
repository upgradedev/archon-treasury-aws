"""Hexagonal ports and the least-privilege gate (STANDARDS A7).

Three roles, three capabilities. Reader can look. Evaluator can propose
a typed ApprovalIntent (a model may drive this port, outside this
package). Writer can move money, and only through ExecutionGate, which
demands the WRITE capability plus a fresh, floor-safe approval digest.
A Reader credential attempting a write is refused here, before any
adapter code runs. Adapters implement these Protocols outside src/kerdon/.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from kerdon.approvals import ApprovalIntent, ApprovalToken, RequestIdLedger, verify_for_execution
from kerdon.errors import CapabilityError
from kerdon.models import TreasurySnapshot


class Capability(Enum):
    READ = "READ"
    EVALUATE = "EVALUATE"
    WRITE = "WRITE"


@dataclass(frozen=True, slots=True)
class Actor:
    actor_id: str
    capabilities: frozenset[Capability]

    def require(self, capability: Capability) -> None:
        if capability not in self.capabilities:
            raise CapabilityError(
                f"actor {self.actor_id} lacks {capability.value}; write refused"
            )


def reader(actor_id: str) -> Actor:
    return Actor(actor_id, frozenset({Capability.READ}))


def evaluator(actor_id: str) -> Actor:
    return Actor(actor_id, frozenset({Capability.READ, Capability.EVALUATE}))


def writer(actor_id: str) -> Actor:
    return Actor(actor_id, frozenset({Capability.WRITE}))


class ReaderPort(Protocol):
    def snapshot(self) -> TreasurySnapshot: ...


class EvaluatorPort(Protocol):
    def propose(self, snapshot: TreasurySnapshot, obligation_id: str) -> ApprovalIntent: ...


class WriterPort(Protocol):
    def execute(self, intent: ApprovalIntent, request_id: str) -> str: ...


@dataclass(slots=True)
class ExecutionGate:
    """The only path from an approval to a money movement."""

    ledger: RequestIdLedger

    def execute(
        self,
        actor: Actor,
        token: ApprovalToken,
        snapshot: TreasurySnapshot,
        write_port: WriterPort,
    ) -> str:
        actor.require(Capability.WRITE)
        request_id = verify_for_execution(token, snapshot, self.ledger)
        return write_port.execute(token.intent, request_id)
