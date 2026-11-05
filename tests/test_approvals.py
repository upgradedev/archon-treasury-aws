"""Changed-evidence invalidation, idempotency locks, and the A7 writer gate."""

import unittest
from dataclasses import replace
from datetime import timedelta

from fixtures import NOW, clean_snapshot, obligation
from kerdon.approvals import (
    ApprovalIntent,
    ApprovalState,
    ApprovalToken,
    RequestIdLedger,
    check_token,
    derive_request_id,
    invalidate_changed,
    operation_sha256,
    verify_for_execution,
)
from kerdon.errors import CapabilityError, DuplicateRequestIdError, ReserveFloorError, StaleApprovalError
from kerdon.money import Money
from kerdon.models import Balance, TreasurySnapshot
from kerdon.ports import ExecutionGate, reader, writer


def make_token(snap, obl, terms="net-14"):
    return ApprovalToken(ApprovalIntent.from_snapshot(snap, obl, terms), "elena-vance", NOW)


class FakeWriter:
    def __init__(self):
        self.calls = []

    def execute(self, intent, request_id):
        self.calls.append((intent.obligation_id, request_id))
        return f"transfer:{request_id}"


class ApprovalsTest(unittest.TestCase):
    def test_digest_stable_and_sensitive(self):
        snap, obl = clean_snapshot(), obligation()
        a, b = make_token(snap, obl), make_token(snap, obl)
        self.assertEqual(a.sha256, b.sha256)
        self.assertNotEqual(a.sha256, make_token(snap, obl, terms="net-30").sha256)

    def test_only_affected_approval_is_invalidated(self):
        # The hero: a EUR deposit lands. EUR approval stales, USD survives.
        usd, eur = obligation(), obligation(
            obligation_id="obl-2", counterparty_id="supplier-b", amount=Money(80_00, "EUR")
        )
        snap = TreasurySnapshot(
            as_of=NOW,
            balances=(Balance("a-usd", Money(1_000_00, "USD")), Balance("a-eur", Money(1_000_00, "EUR"))),
            obligations=(usd, eur),
            reserve_floors=(Money(100_00, "USD"), Money(100_00, "EUR")),
        )
        tokens = (make_token(snap, eur), make_token(snap, usd))  # order must not matter
        deposited = replace(
            snap,
            balances=(Balance("a-usd", Money(1_000_00, "USD")), Balance("a-eur", Money(1_500_00, "EUR"))),
        )
        by_id = {r.token.intent.obligation_id: r.state for r in invalidate_changed(tokens, deposited)}
        self.assertEqual(by_id["obl-1"], ApprovalState.VALID)
        self.assertEqual(by_id["obl-2"], ApprovalState.INVALIDATED)

    def test_stale_execution_is_refused(self):
        snap, obl = clean_snapshot(), obligation()
        token = make_token(snap, obl)
        changed = replace(snap, balances=(Balance("acct-usd", Money(2_000_00, "USD")),))
        self.assertEqual(check_token(token, changed).state, ApprovalState.INVALIDATED)
        with self.assertRaises(StaleApprovalError):
            verify_for_execution(token, changed, RequestIdLedger())

    def test_reserve_floor_execution_is_refused(self):
        obl = obligation()
        tight = TreasurySnapshot(
            as_of=NOW,
            balances=(Balance("acct-usd", Money(120_00, "USD")),),
            obligations=(obl,),
            reserve_floors=(Money(100_00, "USD"),),
        )
        with self.assertRaises(ReserveFloorError):
            verify_for_execution(make_token(tight, obl), tight, RequestIdLedger())

    def test_request_id_retry_stable_revision_fresh(self):
        snap, obl = clean_snapshot(), obligation()
        token = make_token(snap, obl)
        ledger = RequestIdLedger()
        first = verify_for_execution(token, snap, ledger)
        self.assertEqual(first, derive_request_id(operation_sha256(token)))
        self.assertEqual(verify_for_execution(token, snap, ledger), first)  # exact retry
        revised = make_token(snap, obligation(amount=Money(51_00, "USD")))
        self.assertNotEqual(derive_request_id(operation_sha256(revised)), first)

    def test_request_id_collision_and_seven_day_boundary(self):
        ledger = RequestIdLedger()
        ledger.register("req-x", "a" * 64, NOW)
        with self.assertRaises(DuplicateRequestIdError):
            ledger.register("req-x", "b" * 64, NOW + timedelta(days=7) - timedelta(seconds=1))
        ledger.register("req-x", "b" * 64, NOW + timedelta(days=7))  # expired at exactly 7 days

    def test_reader_cannot_write_a7(self):
        snap, obl = clean_snapshot(), obligation()
        fake = FakeWriter()
        gate = ExecutionGate(RequestIdLedger())
        with self.assertRaises(CapabilityError):
            gate.execute(reader("judge-public"), make_token(snap, obl), snap, fake)
        self.assertEqual(fake.calls, [])  # adapter never touched

    def test_writer_executes_once_with_derived_request_id(self):
        snap, obl = clean_snapshot(), obligation()
        fake = FakeWriter()
        token = make_token(snap, obl)
        ref = ExecutionGate(RequestIdLedger()).execute(writer("treasury-writer"), token, snap, fake)
        self.assertEqual(ref, f"transfer:{derive_request_id(token.sha256)}")
        self.assertEqual(len(fake.calls), 1)


if __name__ == "__main__":
    unittest.main()
