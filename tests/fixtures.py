"""Synthetic clean-room fixtures shared by the Phase 1 tests.

Every name, amount, and ID here is invented for tests. No customer data.
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from kerdon.approvals import evidence_sha256_for
from kerdon.money import Money
from kerdon.models import (
    Balance,
    DocKind,
    DocumentEvidence,
    ExecutionRecord,
    FxQuote,
    LedgerEntry,
    Obligation,
    PendingApproval,
    TreasurySnapshot,
)

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def obligation(**kw) -> Obligation:
    base = dict(
        obligation_id="obl-1",
        counterparty_id="supplier-a",
        amount=Money(50_00, "USD"),
        due_at=NOW + timedelta(days=10),
    )
    base.update(kw)
    return Obligation(**base)


def clean_snapshot(**overrides) -> TreasurySnapshot:
    """A snapshot with zero blockers. Tests break one fact at a time."""
    obl = obligation()
    snap = TreasurySnapshot(
        as_of=NOW,
        balances=(Balance("acct-usd", Money(1_000_00, "USD")),),
        obligations=(obl,),
        ledger_entries=(
            LedgerEntry("led-1", "acct-usd", "supplier-a", Money(-50_00, "USD"), NOW - timedelta(days=1)),
            LedgerEntry("led-2", "acct-usd", "client-x", Money(200_00, "USD"), NOW - timedelta(days=1)),
        ),
        documents=(
            DocumentEvidence("doc-1", DocKind.INVOICE, "supplier-a", Money(50_00, "USD"), SHA_A, "INV-1", "obl-1"),
            DocumentEvidence("doc-2", DocKind.DEPOSIT_RECEIPT, "client-x", Money(200_00, "USD"), SHA_B),
        ),
        reserve_floors=(Money(100_00, "USD"),),
    )
    evidence = evidence_sha256_for(snap, obl)
    snap = replace(
        snap,
        pending_approvals=(PendingApproval("obl-1", SHA_C, evidence),),
        executions=(
            ExecutionRecord("exe-1", "obl-1", "req-1", SHA_A, SHA_C, NOW - timedelta(hours=1)),
        ),
    )
    if overrides:
        snap = replace(snap, **overrides)
    return snap


def fx_quote(**kw) -> FxQuote:
    base = dict(
        quote_id="fx-1",
        from_currency="USD",
        to_currency="EUR",
        source_amount=Money(50_00, "USD"),
        rate_numerator=92,
        rate_denominator=100,
        expires_at=NOW + timedelta(hours=4),
    )
    base.update(kw)
    return FxQuote(**base)
