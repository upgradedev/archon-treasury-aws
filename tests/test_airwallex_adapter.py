"""Boundary conversion, fake-transport idempotency, and the webhook hero path."""

import json
import unittest

from adapters.airwallex_client import (
    AdapterError,
    AirwallexClient,
    DuplicateRequestError,
    FakeAirwallexTransport,
    build_deposit_simulation_payload,
    build_transfer_payload,
    parse_major_amount,
    to_airwallex_amount,
)
from adapters.webhook import SignatureError, handle_webhook, sign_payload, verify_signature
from fixtures import NOW, clean_snapshot, obligation
from kerdon.approvals import ApprovalIntent, ApprovalState, ApprovalToken, RequestIdLedger
from kerdon.money import Money
from kerdon.models import Balance, TreasurySnapshot
from kerdon.ports import ExecutionGate, writer

SECRET = "test-webhook-secret"


def make_token(snap, obl):
    return ApprovalToken(ApprovalIntent.from_snapshot(snap, obl, "net-14"), "elena-vance", NOW)


class ConversionTest(unittest.TestCase):
    def test_cents_leave_as_major_string(self):
        # Trap T2: 5000 cents must cross the boundary as "50.00".
        self.assertEqual(to_airwallex_amount(Money(5000, "USD")), "50.00")
        intent = ApprovalIntent.from_snapshot(clean_snapshot(), obligation(), "net-14")
        payload = build_transfer_payload(intent, "req-1", "supplier-a")
        self.assertEqual(payload["amount"], "50.00")
        self.assertEqual(payload["request_id"], "req-1")

    def test_major_string_parses_back_to_cents(self):
        self.assertEqual(parse_major_amount("50.00", "USD"), Money(5000, "USD"))
        self.assertEqual(parse_major_amount("0.05", "EUR"), Money(5, "EUR"))
        self.assertEqual(parse_major_amount("-1.23", "GBP"), Money(-123, "GBP"))
        self.assertEqual(parse_major_amount("7", "USD"), Money(700, "USD"))

    def test_bad_amounts_fail_closed(self):
        for bad in ("1.234", "abc", "", "1,000.00", "9999999999.00"):
            with self.assertRaises(AdapterError, msg=bad):
                parse_major_amount(bad, "USD")
        with self.assertRaises(AdapterError):
            parse_major_amount(50.0, "USD")

    def test_non_positive_deposits_fail_closed(self):
        for cents in (0, -500_00):
            with self.assertRaises(AdapterError):
                build_deposit_simulation_payload("ga-us-1", Money(cents, "USD"))

    def test_deposit_simulation_has_no_currency_field(self):
        # Trap T4: the field would be silently discarded, so never send it.
        payload = build_deposit_simulation_payload("ga-us-1", Money(200_00, "USD"), "Client X")
        self.assertNotIn("currency", payload)
        self.assertEqual(payload["amount"], "200.00")


class FakeTransportTest(unittest.TestCase):
    def test_same_request_is_idempotent(self):
        client = AirwallexClient(FakeAirwallexTransport())
        intent = ApprovalIntent.from_snapshot(clean_snapshot(), obligation(), "net-14")
        first = client.execute(intent, "req-once")
        second = client.execute(intent, "req-once")
        self.assertEqual(first, second)
        self.assertEqual(client.transport.transfer_count, 1)

    def test_same_request_id_new_payload_is_refused(self):
        transport = FakeAirwallexTransport()
        client = AirwallexClient(transport)
        snap = clean_snapshot()
        client.execute(ApprovalIntent.from_snapshot(snap, obligation(), "net-14"), "req-x")
        revised = ApprovalIntent.from_snapshot(snap, obligation(amount=Money(51_00, "USD")), "net-14")
        with self.assertRaises(DuplicateRequestError):
            client.execute(revised, "req-x")
        self.assertEqual(transport.transfer_count, 1)

    def test_writer_gate_executes_through_adapter(self):
        transport = FakeAirwallexTransport()
        snap = clean_snapshot()
        token = make_token(snap, obligation())
        ref = ExecutionGate(RequestIdLedger()).execute(
            writer("treasury-writer"), token, snap, AirwallexClient(transport)
        )
        self.assertEqual(ref, "trn_fake_1")
        self.assertEqual(transport.transfer_count, 1)

    def test_balances_parse_major_strings(self):
        transport = FakeAirwallexTransport(
            balance_rows=[{"account_id": "ga-us-1", "currency": "USD", "amount": "1000.00"}]
        )
        self.assertEqual(
            AirwallexClient(transport).get_balances(),
            (Balance("ga-us-1", Money(100_000, "USD")),),
        )


class WebhookTest(unittest.TestCase):
    def _snap_and_tokens(self):
        usd = obligation()
        eur = obligation(obligation_id="obl-2", counterparty_id="supplier-b", amount=Money(80_00, "EUR"))
        snap = TreasurySnapshot(
            as_of=NOW,
            balances=(Balance("ga-us-1", Money(1_000_00, "USD")), Balance("ga-de-1", Money(1_000_00, "EUR"))),
            obligations=(usd, eur),
            reserve_floors=(Money(100_00, "USD"), Money(100_00, "EUR")),
        )
        return snap, (make_token(snap, usd), make_token(snap, eur))

    def test_signature_round_trip_and_forgery(self):
        body = b'{"id":"evt-1"}'
        self.assertTrue(verify_signature(body, sign_payload(body, SECRET), SECRET))
        self.assertFalse(verify_signature(body, sign_payload(body, "other"), SECRET))
        self.assertFalse(verify_signature(body, None, SECRET))

    def test_bad_signature_refuses_whole_event(self):
        snap, tokens = self._snap_and_tokens()
        body = json.dumps(
            {"id": "evt-1", "data": {"global_account_id": "ga-de-1", "currency": "EUR", "amount": "500.00"}}
        ).encode()
        with self.assertRaises(SignatureError):
            handle_webhook(body, "deadbeef", SECRET, snap, tokens)

    def test_deposit_invalidates_only_affected_currency(self):
        # Hero path through the real boundary: EUR deposit, USD approval survives.
        snap, tokens = self._snap_and_tokens()
        body = json.dumps(
            {"id": "evt-1", "data": {"global_account_id": "ga-de-1", "currency": "EUR", "amount": "500.00"}}
        ).encode()
        updated, results = handle_webhook(body, sign_payload(body, SECRET), SECRET, snap, tokens)
        self.assertEqual(updated.balance_cents("EUR"), 1_500_00)
        self.assertEqual(updated.balance_cents("USD"), 1_000_00)
        by_id = {r.token.intent.obligation_id: r.state for r in results}
        self.assertEqual(by_id["obl-1"], ApprovalState.VALID)
        self.assertEqual(by_id["obl-2"], ApprovalState.INVALIDATED)
        self.assertEqual(snap.balance_cents("EUR"), 1_000_00)  # input untouched

    def test_mismatched_account_currency_in_webhook_refused(self):
        snap, tokens = self._snap_and_tokens()
        bad_body = json.dumps(
            {"id": "evt-bad", "data": {"global_account_id": "ga-us-1", "currency": "EUR", "amount": "500.00"}}
        ).encode()
        with self.assertRaises(AdapterError):
            handle_webhook(bad_body, sign_payload(bad_body, SECRET), SECRET, snap, tokens)


if __name__ == "__main__":
    unittest.main()
