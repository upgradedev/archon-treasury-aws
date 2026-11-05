"""Treasury vocabulary (DDD ubiquitous language, STANDARDS A6).

Nouns match STATE.md section 4: Obligation, LedgerEntry, DocumentEvidence,
FxQuote, Reserve Floor, ApprovalIntent, ExecutionRecord, TreasurySnapshot.
All amounts are Money (integer cents). All timestamps are injected by the
caller; nothing in this package reads a clock, a socket, or a file.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from kerdon.money import Money


class ObligationStatus(Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class DocKind(Enum):
    INVOICE = "INVOICE"
    BILL = "BILL"
    DEPOSIT_RECEIPT = "DEPOSIT_RECEIPT"


class Severity(Enum):
    BLOCKER = "BLOCKER"
    WARNING = "WARNING"


@dataclass(frozen=True, slots=True)
class Obligation:
    obligation_id: str
    counterparty_id: str
    amount: Money
    due_at: datetime | None
    status: ObligationStatus = ObligationStatus.PENDING
    fx_quote_id: str | None = None
    settle_currency: str | None = None

    @property
    def requires_fx(self) -> bool:
        return self.settle_currency is not None and self.settle_currency != self.amount.currency


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """One bank row. Negative cents mean money left the account (debit)."""

    entry_id: str
    account_id: str
    counterparty_id: str
    amount: Money
    booked_at: datetime

    @property
    def is_debit(self) -> bool:
        return self.amount.amount_cents < 0

    @property
    def is_credit(self) -> bool:
        return self.amount.amount_cents > 0


@dataclass(frozen=True, slots=True)
class DocumentEvidence:
    document_id: str
    kind: DocKind
    counterparty_id: str
    amount: Money
    content_sha256: str
    invoice_number: str | None = None
    obligation_id: str | None = None


@dataclass(frozen=True, slots=True)
class FxQuote:
    """Locked FX quote. Rate stays a ratio of two ints; never a fraction type."""

    quote_id: str
    from_currency: str
    to_currency: str
    source_amount: Money
    rate_numerator: int
    rate_denominator: int
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class Balance:
    account_id: str
    amount: Money


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    execution_id: str
    obligation_id: str
    request_id: str
    operation_sha256: str
    approval_sha256: str | None
    executed_at: datetime


@dataclass(frozen=True, slots=True)
class PendingApproval:
    obligation_id: str
    approval_sha256: str
    evidence_sha256: str


@dataclass(frozen=True, slots=True)
class Finding:
    rule_id: str
    severity: Severity
    subject_id: str
    message: str
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class TreasurySnapshot:
    """Immutable evidence set at one instant. Rules and gates read only this."""

    as_of: datetime
    balances: tuple[Balance, ...] = ()
    obligations: tuple[Obligation, ...] = ()
    ledger_entries: tuple[LedgerEntry, ...] = ()
    documents: tuple[DocumentEvidence, ...] = ()
    fx_quotes: tuple[FxQuote, ...] = ()
    executions: tuple[ExecutionRecord, ...] = ()
    pending_approvals: tuple[PendingApproval, ...] = ()
    reserve_floors: tuple[Money, ...] = ()

    def balance_cents(self, currency: str) -> int:
        return sum(b.amount.amount_cents for b in self.balances if b.amount.currency == currency)

    def reserve_floor_cents(self, currency: str) -> int:
        return sum(f.amount_cents for f in self.reserve_floors if f.currency == currency)

    def pending_obligations(self, currency: str | None = None) -> tuple[Obligation, ...]:
        rows = [o for o in self.obligations if o.status is ObligationStatus.PENDING]
        if currency is not None:
            rows = [o for o in rows if o.amount.currency == currency]
        return tuple(sorted(rows, key=lambda o: o.obligation_id))

    def obligation(self, obligation_id: str) -> Obligation | None:
        for row in self.obligations:
            if row.obligation_id == obligation_id:
                return row
        return None

    def fx_quote(self, quote_id: str | None) -> FxQuote | None:
        if quote_id is None:
            return None
        for row in self.fx_quotes:
            if row.quote_id == quote_id:
                return row
        return None
