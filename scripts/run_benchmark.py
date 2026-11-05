"""Frozen completeness and invalidation benchmark. Stdlib only, offline.

Method, stated so the number can be challenged: every case is hand-labelled
before any engine runs. A broken case is correct when its labelled rule (or
invalidation verdict) is detected. A clean case is correct when zero
blockers fire. The baseline is a naive single-pass amount matcher: it flags
only a first-invoice vs first-obligation amount mismatch and never
invalidates an approval. It stands in for unconstrained one-pass matching;
it is not a hosted LLM measurement, and this script never claims that.

Run: PYTHONPATH=src python scripts/run_benchmark.py
"""

import json
import sys
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kerdon.approvals import ApprovalIntent, ApprovalState, ApprovalToken, check_token, evidence_sha256_for
from kerdon.completeness import evaluate
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
    Severity,
    TreasurySnapshot,
)

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
SHA = "a" * 64
SHA_B = "b" * 64


def base(cents=50_00, currency="USD", balance=1_000_00):
    obl = Obligation("obl-1", "supplier-a", Money(cents, currency), NOW + timedelta(days=10))
    snap = TreasurySnapshot(
        as_of=NOW,
        balances=(Balance(f"acct-{currency}", Money(balance, currency)),),
        obligations=(obl,),
        ledger_entries=(
            LedgerEntry("led-1", f"acct-{currency}", "supplier-a", Money(-cents, currency), NOW - timedelta(days=1)),
            LedgerEntry("led-2", f"acct-{currency}", "client-x", Money(200_00, currency), NOW - timedelta(days=1)),
        ),
        documents=(
            DocumentEvidence("doc-1", DocKind.INVOICE, "supplier-a", Money(cents, currency), SHA, "INV-1", "obl-1"),
            DocumentEvidence("doc-2", DocKind.DEPOSIT_RECEIPT, "client-x", Money(200_00, currency), SHA_B),
        ),
        reserve_floors=(Money(100_00, currency),),
    )
    approval = PendingApproval("obl-1", "c" * 64, evidence_sha256_for(snap, obl))
    return replace(
        snap,
        pending_approvals=(approval,),
        executions=(ExecutionRecord("exe-1", "obl-1", "req-1", SHA, "c" * 64, NOW - timedelta(hours=1)),),
    )


def rule_cases():
    cases = []  # (name, snapshot, expected_rule_or_None_for_clean)
    for currency in ("USD", "EUR", "GBP"):
        for cents in (10_00, 50_00, 123_00):
            clean = base(cents, currency)
            cases.append((f"clean-{currency}-{cents}", clean, None))
            no_inv = replace(clean, documents=tuple(d for d in clean.documents if d.kind is not DocKind.INVOICE))
            cases.append((f"r01-{currency}-{cents}", no_inv, "R01"))
            no_dep = replace(clean, documents=tuple(d for d in clean.documents if d.kind is not DocKind.DEPOSIT_RECEIPT))
            cases.append((f"r02-{currency}-{cents}", no_dep, "R02"))
            bad_doc = DocumentEvidence("doc-1", DocKind.INVOICE, "supplier-a", Money(cents + 100, currency), SHA, "INV-1", "obl-1")
            cases.append((f"r15-{currency}-{cents}", replace(clean, documents=(bad_doc,) + clean.documents[1:]), "R15"))
            tight = base(cents, currency, balance=cents + 90_00)
            cases.append((f"r09-{currency}-{cents}", tight, "R09"))
    s = base()
    obl = s.obligations[0]
    singles = [
        ("R03", replace(s, documents=s.documents + (DocumentEvidence("d9", DocKind.BILL, "supplier-a", Money(50_00, "USD"), SHA_B, "INV-1", "obl-1"),))),
        ("R04", replace(s, documents=s.documents + (DocumentEvidence("d9", DocKind.INVOICE, "nobody", Money(1_00, "USD"), SHA_B, "INV-9"),))),
        ("R05", replace(s, obligations=(replace(obl, counterparty_id=" "),))),
        ("R06", replace(s, obligations=(replace(obl, due_at=None),))),
        ("R07", replace(s, obligations=(replace(obl, due_at=NOW - timedelta(days=1)),))),
        ("R08", replace(s, obligations=(replace(obl, due_at=NOW + timedelta(hours=5)),), balances=(Balance("acct-USD", Money(1_00, "USD")),))),
        ("R10", replace(s, balances=(Balance("acct-USD", Money(1_00, "USD")),))),
        ("R11", replace(s, obligations=(replace(obl, settle_currency="EUR"),))),
        ("R12", replace(s, fx_quotes=(FxQuote("fx-1", "USD", "EUR", Money(50_00, "USD"), 92, 100, NOW - timedelta(minutes=1)),))),
        ("R13", replace(s, obligations=(replace(obl, settle_currency="EUR", fx_quote_id="fx-1"),), fx_quotes=(FxQuote("fx-1", "USD", "EUR", Money(49_00, "USD"), 92, 100, NOW + timedelta(hours=2)),))),
        ("R14", replace(s, executions=s.executions + (ExecutionRecord("e9", "obl-1", "req-1", SHA_B, "c" * 64, NOW),))),
        ("R16", replace(s, documents=(DocumentEvidence("doc-1", DocKind.INVOICE, "supplier-a", Money(50_00, "EUR"), SHA, "INV-1", "obl-1"),) + s.documents[1:])),
        ("R17", replace(s, documents=(DocumentEvidence("doc-1", DocKind.INVOICE, "supplier-a", Money(50_00, "USD"), "bad", "INV-1", "obl-1"),) + s.documents[1:])),
        ("R18", replace(s, pending_approvals=(PendingApproval("obl-1", "c" * 64, SHA),))),
        ("R19", replace(s, ledger_entries=s.ledger_entries + (LedgerEntry("l9", "acct-USD", "supplier-a", Money(-50_00, "USD"), NOW - timedelta(days=1)),))),
        ("R20", replace(s, obligations=(replace(obl, amount=Money(0, "USD")),))),
        ("R21", replace(s, executions=s.executions + (ExecutionRecord("e9", "obl-1", "req-9", SHA, None, NOW),))),
    ]
    cases += [(f"single-{rule}", snap, rule) for rule, snap in singles]
    return cases


def invalidation_cases():
    cases = []  # (name, snapshot, token, expect_invalidated)
    for currency in ("USD", "EUR", "GBP"):
        for delta in (100_00, 500_00):
            snap = base(50_00, currency)
            token = ApprovalToken(ApprovalIntent.from_snapshot(snap, snap.obligations[0], "t"), "bench", NOW)
            grown = replace(snap, balances=(Balance(f"acct-{currency}", Money(1_000_00 + delta, currency)),))
            cases.append((f"inv-same-{currency}-{delta}", grown, token, True))
            other = "EUR" if currency != "EUR" else "USD"
            shifted = replace(snap, balances=snap.balances + (Balance(f"acct-{other}", Money(delta, other)),))
            cases.append((f"inv-other-{currency}-{delta}", shifted, token, False))
    return cases


def baseline_rule_verdict(snapshot, expected_rule):
    docs = [d for d in snapshot.documents if d.kind is DocKind.INVOICE]
    flagged = set()
    if docs and snapshot.obligations and docs[0].amount.amount_cents != snapshot.obligations[0].amount.amount_cents:
        flagged.add("R15")
    return (expected_rule in flagged) if expected_rule else (not flagged)


def run_benchmark() -> dict:
    rules = rule_cases()
    inv = invalidation_cases()
    start = time.perf_counter()
    engine_ok = 0
    baseline_ok = 0
    for _name, snap, expected in rules:
        findings = evaluate(snap)
        found = {f.rule_id for f in findings}
        blockers = [f for f in findings if f.severity is Severity.BLOCKER]
        engine_ok += int((expected in found) if expected else (not blockers))
        baseline_ok += int(baseline_rule_verdict(snap, expected))
    for _name, snap, token, expect_invalidated in inv:
        engine_ok += int((check_token(token, snap).state is ApprovalState.INVALIDATED) == expect_invalidated)
        baseline_ok += int(expect_invalidated is False)  # baseline never invalidates
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    total = len(rules) + len(inv)
    return {
        "cases": total,
        "rule_cases": len(rules),
        "invalidation_cases": len(inv),
        "engine_correct": engine_ok,
        "baseline_correct": baseline_ok,
        "engine_accuracy": f"{engine_ok}/{total}",
        "baseline_accuracy": f"{baseline_ok}/{total}",
        "elapsed_ms": elapsed_ms,
        "baseline_kind": "naive single-pass amount matcher (not a hosted LLM)",
    }


if __name__ == "__main__":
    print(json.dumps(run_benchmark(), indent=2))
