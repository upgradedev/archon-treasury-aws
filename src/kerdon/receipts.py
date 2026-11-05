"""Merkle-sealed accessible approval receipts (Volcan / Aletheia shape).

A receipt is a short list of plain sentences a screen reader or a speech
synth can read aloud without markup. Amounts render in major units with
the cent count beside them (Trap T2), so a listener hears the same number
the Airwallex boundary will receive. The Merkle root seals the exact
lines: change one character in any line and verification fails.

Merkle convention: leaf = SHA-256(line). Parents pair left to right.
An odd last node pairs with itself. Proofs list (sibling, side) steps.
"""

import hashlib
from dataclasses import dataclass

from kerdon.approvals import ApprovalToken, reserve_after_cents
from kerdon.errors import ReceiptError
from kerdon.money import Money
from kerdon.models import TreasurySnapshot


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pair(left: str, right: str) -> str:
    return _hash(f"{left}:{right}")


def merkle_root(lines: tuple[str, ...]) -> str:
    if not lines:
        raise ReceiptError("receipt needs at least one line")
    level = [_hash(line) for line in lines]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(_pair(left, right))
        level = nxt
    return level[0]


@dataclass(frozen=True, slots=True)
class ProofStep:
    sibling_sha256: str
    sibling_on_left: bool


def merkle_proof(lines: tuple[str, ...], leaf_index: int) -> tuple[ProofStep, ...]:
    if leaf_index < 0 or leaf_index >= len(lines):
        raise ReceiptError(f"leaf index {leaf_index} out of range for {len(lines)} lines")
    level = [_hash(line) for line in lines]
    steps: list[ProofStep] = []
    idx = leaf_index
    while len(level) > 1:
        if idx % 2 == 0:
            sibling = level[idx + 1] if idx + 1 < len(level) else level[idx]
            steps.append(ProofStep(sibling, False))
        else:
            steps.append(ProofStep(level[idx - 1], True))
        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(_pair(left, right))
        level = nxt
        idx //= 2
    return tuple(steps)


def verify_proof(line: str, proof: tuple[ProofStep, ...], expected_root: str) -> bool:
    node = _hash(line)
    for step in proof:
        node = _pair(step.sibling_sha256, node) if step.sibling_on_left else _pair(node, step.sibling_sha256)
    return node == expected_root


@dataclass(frozen=True, slots=True)
class SpokenReceipt:
    lines: tuple[str, ...]
    root_sha256: str
    approval_sha256: str

    @property
    def spoken_text(self) -> str:
        """One string for speech synthesis. Sentences stay short on purpose."""
        return " ".join(self.lines)

    @property
    def aria_label(self) -> str:
        return self.spoken_text

    @property
    def braille_transcript(self) -> str:
        """Plain ASCII lines, one per row, safe for refreshable Braille displays."""
        return "\n".join(self.lines)

    def proof_for(self, leaf_index: int) -> tuple[ProofStep, ...]:
        return merkle_proof(self.lines, leaf_index)

    def verify(self) -> bool:
        return merkle_root(self.lines) == self.root_sha256


def build_receipt(token: ApprovalToken, snapshot: TreasurySnapshot) -> SpokenReceipt:
    intent = token.intent
    amount = Money(intent.amount_cents, intent.currency)
    after_cents = reserve_after_cents(snapshot, intent)
    after = Money(after_cents, intent.currency)
    floor = Money(snapshot.reserve_floor_cents(intent.currency), intent.currency)
    lines = (
        "Archon Treasury approval receipt.",
        f"Pay counterparty {intent.counterparty_id}.",
        f"Amount {amount.spoken()}.",
        f"Obligation {intent.obligation_id}.",
        f"Balance after payment {after.spoken()}.",
        f"Reserve floor {floor.spoken()}.",
        f"Approved by {token.approver_id}.",
        f"Approval digest {token.sha256}.",
        f"Evidence digest {intent.evidence_sha256}.",
    )
    return SpokenReceipt(lines=lines, root_sha256=merkle_root(lines), approval_sha256=token.sha256)
