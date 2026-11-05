"""21 deterministic completeness rules: what is missing, never a guess.

Clean-room Phase 1 rule set. STATE.md section 4 names the source shape
(bank debit without supplier invoice, unbooked client deposit, duplicate
bill) and the source repo named there is not present in this workspace, so
the 21 rules below are defined here, each with a stable ID (R01 to R21),
and verified by tests/test_completeness.py and scripts/verify_gates.py.

Every rule is a pure function of TreasurySnapshot. Findings sort by
(rule_id, subject_id) so two runs over the same snapshot are identical.
Models may explain a finding. Only this code may create one.
"""

from datetime import timedelta

from kerdon.approvals import evidence_sha256_for
from kerdon.models import (
    DocKind,
    Finding,
    ObligationStatus,
    Severity,
    TreasurySnapshot,
)

_HEX = set("0123456789abcdef")


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(c in _HEX for c in value.lower())


def _block(rule_id: str, subject: str, message: str, refs: tuple[str, ...] = ()) -> Finding:
    return Finding(rule_id, Severity.BLOCKER, subject, message, refs)


def _warn(rule_id: str, subject: str, message: str, refs: tuple[str, ...] = ()) -> Finding:
    return Finding(rule_id, Severity.WARNING, subject, message, refs)


def _r01(s: TreasurySnapshot) -> list[Finding]:
    out = []
    invoices = [d for d in s.documents if d.kind in (DocKind.INVOICE, DocKind.BILL)]
    for e in s.ledger_entries:
        if not e.is_debit:
            continue
        matched = any(
            d.counterparty_id == e.counterparty_id
            and d.amount.currency == e.amount.currency
            and d.amount.amount_cents == abs(e.amount.amount_cents)
            for d in invoices
        )
        if not matched:
            out.append(_block("R01", e.entry_id, "Bank debit has no matching supplier invoice.", (e.entry_id,)))
    return out


def _r02(s: TreasurySnapshot) -> list[Finding]:
    out = []
    receipts = [d for d in s.documents if d.kind is DocKind.DEPOSIT_RECEIPT]
    for e in s.ledger_entries:
        if not e.is_credit:
            continue
        matched = any(
            d.counterparty_id == e.counterparty_id
            and d.amount.currency == e.amount.currency
            and d.amount.amount_cents == e.amount.amount_cents
            for d in receipts
        )
        if not matched:
            out.append(_block("R02", e.entry_id, "Client deposit is on the bank row but not booked.", (e.entry_id,)))
    return out


def _r03(s: TreasurySnapshot) -> list[Finding]:
    out = []
    seen: dict[tuple[str, str], str] = {}
    for d in sorted(s.documents, key=lambda x: x.document_id):
        if d.kind not in (DocKind.INVOICE, DocKind.BILL) or not d.invoice_number:
            continue
        key = (d.counterparty_id, d.invoice_number)
        if key in seen:
            out.append(_block("R03", d.document_id, "Duplicate bill: same counterparty and invoice number.", (seen[key], d.document_id)))
        else:
            seen[key] = d.document_id
    return out


def _r04(s: TreasurySnapshot) -> list[Finding]:
    known = {o.obligation_id for o in s.obligations}
    counterparties = {o.counterparty_id for o in s.obligations}
    return [
        _warn("R04", d.document_id, "Invoice has no matching obligation.", (d.document_id,))
        for d in s.documents
        if d.kind in (DocKind.INVOICE, DocKind.BILL)
        and d.obligation_id not in known
        and d.counterparty_id not in counterparties
    ]


def _r05(s: TreasurySnapshot) -> list[Finding]:
    return [
        _block("R05", o.obligation_id, "Obligation is missing its counterparty.", (o.obligation_id,))
        for o in s.obligations
        if not o.counterparty_id.strip()
    ]


def _r06(s: TreasurySnapshot) -> list[Finding]:
    return [
        _warn("R06", o.obligation_id, "Obligation is missing its due date.", (o.obligation_id,))
        for o in s.obligations
        if o.status is ObligationStatus.PENDING and o.due_at is None
    ]


def _r07(s: TreasurySnapshot) -> list[Finding]:
    return [
        _block("R07", o.obligation_id, "Obligation is overdue and still pending.", (o.obligation_id,))
        for o in s.obligations
        if o.status is ObligationStatus.PENDING and o.due_at is not None and o.due_at < s.as_of
    ]


def _r08(s: TreasurySnapshot) -> list[Finding]:
    horizon = s.as_of + timedelta(hours=72)
    out = []
    for o in s.obligations:
        if o.status is not ObligationStatus.PENDING or o.due_at is None:
            continue
        if s.as_of <= o.due_at <= horizon and s.balance_cents(o.amount.currency) < o.amount.amount_cents:
            out.append(_block("R08", o.obligation_id, "Due within 72 hours and the currency balance cannot cover it.", (o.obligation_id,)))
    return out


def _r09(s: TreasurySnapshot) -> list[Finding]:
    out = []
    currencies = sorted({f.currency for f in s.reserve_floors})
    for cur in currencies:
        pending = sum(o.amount.amount_cents for o in s.pending_obligations(cur))
        if s.balance_cents(cur) - pending < s.reserve_floor_cents(cur):
            out.append(_block("R09", f"reserve:{cur}", f"Pending {cur} payouts would breach the reserve floor.", (cur,)))
    return out


def _r10(s: TreasurySnapshot) -> list[Finding]:
    return [
        _block("R10", o.obligation_id, "Currency balance is smaller than this single obligation.", (o.obligation_id,))
        for o in s.obligations
        if o.status is ObligationStatus.PENDING
        and s.balance_cents(o.amount.currency) < o.amount.amount_cents
    ]


def _r11(s: TreasurySnapshot) -> list[Finding]:
    out = []
    for o in s.obligations:
        if o.status is ObligationStatus.PENDING and o.requires_fx:
            if o.fx_quote_id is None or s.fx_quote(o.fx_quote_id) is None:
                out.append(_block("R11", o.obligation_id, "Cross-currency payout has no locked FX quote.", (o.obligation_id,)))
    return out


def _r12(s: TreasurySnapshot) -> list[Finding]:
    return [
        _block("R12", q.quote_id, "FX quote has expired.", (q.quote_id,))
        for q in s.fx_quotes
        if q.expires_at <= s.as_of
    ]


def _r13(s: TreasurySnapshot) -> list[Finding]:
    out = []
    for o in s.obligations:
        q = s.fx_quote(o.fx_quote_id)
        if q is not None and (
            q.source_amount.amount_cents != o.amount.amount_cents
            or q.source_amount.currency != o.amount.currency
        ):
            out.append(_block("R13", o.obligation_id, "FX quote amount does not match the obligation.", (o.obligation_id, q.quote_id)))
    return out


def _r14(s: TreasurySnapshot) -> list[Finding]:
    out = []
    seen: dict[str, str] = {}
    for x in sorted(s.executions, key=lambda r: r.execution_id):
        prior = seen.get(x.request_id)
        if prior is not None and prior != x.operation_sha256:
            out.append(_block("R14", x.execution_id, "One request_id is bound to two different payloads.", (x.execution_id, x.request_id)))
        seen.setdefault(x.request_id, x.operation_sha256)
    return out


def _r15(s: TreasurySnapshot) -> list[Finding]:
    out = []
    for d in s.documents:
        if d.obligation_id is None:
            continue
        o = s.obligation(d.obligation_id)
        if o is not None and d.amount.amount_cents != o.amount.amount_cents:
            out.append(_block("R15", d.document_id, "Invoice amount does not match its obligation.", (d.document_id, o.obligation_id)))
    return out


def _r16(s: TreasurySnapshot) -> list[Finding]:
    out = []
    for d in s.documents:
        if d.obligation_id is None:
            continue
        o = s.obligation(d.obligation_id)
        if o is not None and d.amount.currency != o.amount.currency:
            out.append(_block("R16", d.document_id, "Document currency does not match its obligation currency.", (d.document_id, o.obligation_id)))
    return out


def _r17(s: TreasurySnapshot) -> list[Finding]:
    return [
        _block("R17", d.document_id, "Document has no valid SHA-256 content hash.", (d.document_id,))
        for d in s.documents
        if not _is_sha256(d.content_sha256)
    ]


def _r18(s: TreasurySnapshot) -> list[Finding]:
    out = []
    for p in s.pending_approvals:
        o = s.obligation(p.obligation_id)
        if o is None or (
            o.status is ObligationStatus.PENDING
            and evidence_sha256_for(s, o) != p.evidence_sha256
        ):
            out.append(_block("R18", p.obligation_id, "Pending approval evidence is stale and must be re-approved.", (p.obligation_id, p.approval_sha256)))
    return out


def _r19(s: TreasurySnapshot) -> list[Finding]:
    out = []
    seen: dict[tuple, str] = {}
    for e in sorted(s.ledger_entries, key=lambda r: r.entry_id):
        key = (e.account_id, e.counterparty_id, e.amount.currency, e.amount.amount_cents, e.booked_at.isoformat())
        if key in seen and seen[key] != e.entry_id:
            out.append(_warn("R19", e.entry_id, "Bank row looks like an exact duplicate of another row.", (seen[key], e.entry_id)))
        seen.setdefault(key, e.entry_id)
    return out


def _r20(s: TreasurySnapshot) -> list[Finding]:
    out = [
        _block("R20", o.obligation_id, "Obligation amount must be greater than zero cents.", (o.obligation_id,))
        for o in s.obligations
        if o.amount.amount_cents <= 0
    ]
    out += [
        _block("R20", d.document_id, "Document amount must be greater than zero cents.", (d.document_id,))
        for d in s.documents
        if d.amount.amount_cents <= 0
    ]
    return out


def _r21(s: TreasurySnapshot) -> list[Finding]:
    # Approvals on record for audit. An execution must cite one of them.
    approved = {p.approval_sha256 for p in s.pending_approvals}
    return [
        _block("R21", x.execution_id, "Execution has no matching approval digest.", (x.execution_id,))
        for x in s.executions
        if not x.approval_sha256 or x.approval_sha256 not in approved
    ]


RULES = (
    ("R01", "bank-debit-without-invoice", _r01),
    ("R02", "unbooked-client-deposit", _r02),
    ("R03", "duplicate-bill", _r03),
    ("R04", "invoice-without-obligation", _r04),
    ("R05", "obligation-missing-counterparty", _r05),
    ("R06", "obligation-missing-due-date", _r06),
    ("R07", "obligation-overdue", _r07),
    ("R08", "due-within-72h-unfunded", _r08),
    ("R09", "reserve-floor-breach", _r09),
    ("R10", "insufficient-balance", _r10),
    ("R11", "fx-quote-missing", _r11),
    ("R12", "fx-quote-expired", _r12),
    ("R13", "fx-quote-amount-mismatch", _r13),
    ("R14", "duplicate-request-id-payload", _r14),
    ("R15", "invoice-amount-mismatch", _r15),
    ("R16", "currency-mismatch", _r16),
    ("R17", "missing-evidence-hash", _r17),
    ("R18", "stale-approval-evidence", _r18),
    ("R19", "duplicate-ledger-entry", _r19),
    ("R20", "non-positive-amount", _r20),
    ("R21", "unapproved-execution", _r21),
)

RULE_IDS = tuple(r[0] for r in RULES)


def evaluate(snapshot: TreasurySnapshot) -> tuple[Finding, ...]:
    """Run all 21 rules. Same snapshot in, same findings out, same order."""
    findings: list[Finding] = []
    for _rule_id, _name, fn in RULES:
        findings.extend(fn(snapshot))
    return tuple(sorted(findings, key=lambda f: (f.rule_id, f.subject_id)))


def blockers(snapshot: TreasurySnapshot) -> tuple[Finding, ...]:
    return tuple(f for f in evaluate(snapshot) if f.severity is Severity.BLOCKER)


def is_complete(snapshot: TreasurySnapshot) -> bool:
    return len(blockers(snapshot)) == 0
