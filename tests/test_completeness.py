"""One firing test per rule R01-R21, plus a clean fixture and determinism."""

import unittest
from dataclasses import replace
from datetime import timedelta

from fixtures import NOW, SHA_A, SHA_B, clean_snapshot, fx_quote, obligation
from kerdon.completeness import RULE_IDS, blockers, evaluate, is_complete
from kerdon.money import Money
from kerdon.models import (
    Balance,
    DocKind,
    DocumentEvidence,
    ExecutionRecord,
    LedgerEntry,
    PendingApproval,
)


def rule_ids(snap) -> set[str]:
    return {f.rule_id for f in evaluate(snap)}


class CompletenessTest(unittest.TestCase):
    def test_twenty_one_rules_registered(self):
        self.assertEqual(RULE_IDS, tuple(f"R{i:02d}" for i in range(1, 22)))

    def test_clean_snapshot_has_no_blockers(self):
        snap = clean_snapshot()
        self.assertEqual(blockers(snap), ())
        self.assertTrue(is_complete(snap))

    def test_deterministic_ordering(self):
        snap = clean_snapshot(documents=())
        self.assertEqual(evaluate(snap), evaluate(snap))

    def test_r01_debit_without_invoice(self):
        docs = tuple(d for d in clean_snapshot().documents if d.kind is not DocKind.INVOICE)
        self.assertIn("R01", rule_ids(clean_snapshot(documents=docs)))

    def test_r02_unbooked_deposit(self):
        docs = tuple(d for d in clean_snapshot().documents if d.kind is not DocKind.DEPOSIT_RECEIPT)
        self.assertIn("R02", rule_ids(clean_snapshot(documents=docs)))

    def test_r03_duplicate_bill(self):
        dup = DocumentEvidence("doc-9", DocKind.BILL, "supplier-a", Money(50_00, "USD"), SHA_B, "INV-1", "obl-1")
        snap = clean_snapshot()
        self.assertIn("R03", rule_ids(replace(snap, documents=snap.documents + (dup,))))

    def test_r04_invoice_without_obligation(self):
        stray = DocumentEvidence("doc-9", DocKind.INVOICE, "nobody", Money(10_00, "USD"), SHA_B, "INV-9")
        snap = clean_snapshot()
        self.assertIn("R04", rule_ids(replace(snap, documents=snap.documents + (stray,))))

    def test_r05_missing_counterparty(self):
        snap = clean_snapshot(obligations=(obligation(counterparty_id=" "),))
        self.assertIn("R05", rule_ids(snap))

    def test_r06_missing_due_date(self):
        snap = clean_snapshot(obligations=(obligation(due_at=None),))
        self.assertIn("R06", rule_ids(snap))

    def test_r07_overdue(self):
        snap = clean_snapshot(obligations=(obligation(due_at=NOW - timedelta(days=1)),))
        self.assertIn("R07", rule_ids(snap))

    def test_r08_due_within_72h_unfunded(self):
        snap = clean_snapshot(
            obligations=(obligation(due_at=NOW + timedelta(hours=24)),),
            balances=(Balance("acct-usd", Money(10_00, "USD")),),
        )
        self.assertIn("R08", rule_ids(snap))

    def test_r09_reserve_floor_and_offset_window(self):
        # C6 offset discipline: same floor and pending, balance starts elsewhere.
        breach = clean_snapshot(balances=(Balance("acct-usd", Money(120_00, "USD")),))
        self.assertIn("R09", rule_ids(breach))  # 120.00 - 50.00 < 100.00 floor
        funded = clean_snapshot(balances=(Balance("acct-usd", Money(170_00, "USD")),))
        self.assertNotIn("R09", rule_ids(funded))  # shifted start: no breach

    def test_r10_insufficient_balance(self):
        snap = clean_snapshot(balances=(Balance("acct-usd", Money(40_00, "USD")),))
        self.assertIn("R10", rule_ids(snap))

    def test_r11_fx_missing(self):
        snap = clean_snapshot(obligations=(obligation(settle_currency="EUR"),))
        self.assertIn("R11", rule_ids(snap))

    def test_r12_fx_expired(self):
        snap = clean_snapshot(fx_quotes=(fx_quote(expires_at=NOW - timedelta(minutes=1)),))
        self.assertIn("R12", rule_ids(snap))

    def test_r13_fx_amount_mismatch(self):
        snap = clean_snapshot(
            obligations=(obligation(settle_currency="EUR", fx_quote_id="fx-1"),),
            fx_quotes=(fx_quote(source_amount=Money(49_00, "USD")),),
        )
        self.assertIn("R13", rule_ids(snap))

    def test_r14_request_id_two_payloads(self):
        clash = ExecutionRecord("exe-2", "obl-1", "req-1", SHA_B, "c" * 64, NOW)
        snap = clean_snapshot()
        self.assertIn("R14", rule_ids(replace(snap, executions=snap.executions + (clash,))))

    def test_r15_amount_mismatch(self):
        bad = DocumentEvidence("doc-1", DocKind.INVOICE, "supplier-a", Money(51_00, "USD"), SHA_A, "INV-1", "obl-1")
        snap = clean_snapshot()
        docs = (bad,) + snap.documents[1:]
        self.assertIn("R15", rule_ids(replace(snap, documents=docs)))

    def test_r16_currency_mismatch(self):
        bad = DocumentEvidence("doc-1", DocKind.INVOICE, "supplier-a", Money(50_00, "EUR"), SHA_A, "INV-1", "obl-1")
        snap = clean_snapshot()
        docs = (bad,) + snap.documents[1:]
        self.assertIn("R16", rule_ids(replace(snap, documents=docs)))

    def test_r17_bad_hash(self):
        bad = DocumentEvidence("doc-1", DocKind.INVOICE, "supplier-a", Money(50_00, "USD"), "not-a-hash", "INV-1", "obl-1")
        snap = clean_snapshot()
        docs = (bad,) + snap.documents[1:]
        self.assertIn("R17", rule_ids(replace(snap, documents=docs)))

    def test_r18_stale_approval(self):
        snap = clean_snapshot(pending_approvals=(PendingApproval("obl-1", "c" * 64, SHA_A),))
        self.assertIn("R18", rule_ids(snap))

    def test_r19_duplicate_bank_row(self):
        dup = LedgerEntry("led-9", "acct-usd", "supplier-a", Money(-50_00, "USD"), NOW - timedelta(days=1))
        snap = clean_snapshot()
        self.assertIn("R19", rule_ids(replace(snap, ledger_entries=snap.ledger_entries + (dup,))))

    def test_r20_non_positive_amount(self):
        snap = clean_snapshot(obligations=(obligation(amount=Money(0, "USD")),))
        self.assertIn("R20", rule_ids(snap))

    def test_r21_unapproved_execution(self):
        rogue = ExecutionRecord("exe-9", "obl-1", "req-9", SHA_A, None, NOW)
        snap = clean_snapshot()
        self.assertIn("R21", rule_ids(replace(snap, executions=snap.executions + (rogue,))))


if __name__ == "__main__":
    unittest.main()
