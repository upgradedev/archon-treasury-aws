"""Evaluator port stand-in: parse an invoice, compare evidence, propose.

The deployed Evaluator runs a model on Bedrock behind this same port. Its
contract never changes: unstructured text in, one typed ApprovalIntent (or
a refusal with reasons) out. It cannot approve and cannot execute; only a
human approval token plus the deterministic Writer gate can move money.
This offline parser keeps that contract testable without any SDK.
"""

import re
from dataclasses import dataclass

from adapters.airwallex_client import parse_major_amount
from kerdon.approvals import ApprovalIntent
from kerdon.errors import DomainError
from kerdon.models import TreasurySnapshot

_AMOUNT_RE = re.compile(r"\b(USD|EUR|GBP)\s+(\d{1,9}(?:\.\d{1,2})?)\b")
_COUNTERPARTY_RE = re.compile(r"[Cc]ounterparty[:\s]+([A-Za-z0-9][A-Za-z0-9\- ]{0,40})")


@dataclass(frozen=True, slots=True)
class ParsedInvoice:
    currency: str
    amount_cents: int
    counterparty_id: str


def parse_invoice_text(text: str) -> ParsedInvoice:
    amount = _AMOUNT_RE.search(text)
    party = _COUNTERPARTY_RE.search(text)
    if amount is None or party is None:
        raise DomainError("invoice text is missing a currency amount or a counterparty")
    money = parse_major_amount(amount.group(2), amount.group(1))
    slug = party.group(1).strip().lower().replace(" ", "-")
    return ParsedInvoice(money.currency, money.amount_cents, slug)


def propose_from_parsed(
    snapshot: TreasurySnapshot, obligation_id: str, parsed: ParsedInvoice
) -> ApprovalIntent:
    """Shared deterministic comparison. Any extractor, human or model, must pass it."""
    obligation = snapshot.obligation(obligation_id)
    if obligation is None:
        raise DomainError(f"unknown obligation {obligation_id!r}")
    problems = []
    if parsed.amount_cents != obligation.amount.amount_cents:
        problems.append("invoice amount differs from the obligation")
    if parsed.currency != obligation.amount.currency:
        problems.append("invoice currency differs from the obligation")
    if parsed.counterparty_id != obligation.counterparty_id:
        problems.append("invoice counterparty differs from the obligation")
    if problems:
        raise DomainError("evaluator refuses to propose: " + "; ".join(problems))
    return ApprovalIntent.from_snapshot(snapshot, obligation, "evaluator-proposal-v1")


class DeterministicEvaluator:
    """Implements kerdon EvaluatorPort without a model, for offline runs."""

    def propose_from_text(
        self, snapshot: TreasurySnapshot, obligation_id: str, invoice_text: str
    ) -> ApprovalIntent:
        return propose_from_parsed(snapshot, obligation_id, parse_invoice_text(invoice_text))

    def propose(self, snapshot: TreasurySnapshot, obligation_id: str) -> ApprovalIntent:
        obligation = snapshot.obligation(obligation_id)
        if obligation is None:
            raise DomainError(f"unknown obligation {obligation_id!r}")
        return ApprovalIntent.from_snapshot(snapshot, obligation, "evaluator-proposal-v1")
