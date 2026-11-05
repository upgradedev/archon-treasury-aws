"""Metal USDZ caps under price moves, and the Evaluator proposal contract."""

import unittest

from adapters.airwallex_client import AdapterError
from adapters.evaluator import DeterministicEvaluator, parse_invoice_text
from adapters.metal_client import AgentBudget, FakeMetalTransport, MetalSpendGovernor
from fixtures import clean_snapshot
from kerdon.errors import DomainError
from kerdon.money import Money


def governor():
    return MetalSpendGovernor(
        total_budget=Money(100_00, "USDZ"),
        budgets=(
            AgentBudget("agent-fx", 50, Money(25, "USDZ")),
            AgentBudget("agent-docs", 30, Money(10, "USDZ")),
            AgentBudget("agent-watch", 20, Money(5, "USDZ")),
        ),
        transport=FakeMetalTransport(),
    )


class MetalTest(unittest.TestCase):
    def test_caps_derive_from_weights_and_price(self):
        g = governor()
        self.assertEqual(g.allowance_cents("agent-fx"), 50_00)
        self.assertEqual(g.call_cap("agent-fx"), 200)  # 5000 // 25
        self.assertEqual(g.call_cap("agent-watch"), 400)  # 2000 // 5

    def test_payment_refused_at_cap(self):
        g = MetalSpendGovernor(
            total_budget=Money(100, "USDZ"),
            budgets=(AgentBudget("only", 100, Money(60, "USDZ")),),
            transport=FakeMetalTransport(),
        )
        self.assertEqual(g.pay_for_call("only", "call-1"), "mtl_fake_1")
        with self.assertRaises(AdapterError):
            g.pay_for_call("only", "call-2")  # cap is 1 call at this price
        self.assertEqual(g.spent_cents("only"), 60)

    def test_price_rise_shrinks_only_that_agents_cap(self):
        g = governor()
        rows = g.rebalance({"agent-fx": Money(50, "USDZ")})
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["old_call_cap"], rows[0]["new_call_cap"]), (200, 100))
        self.assertEqual(g.call_cap("agent-docs"), 300)  # untouched

    def test_weights_must_sum_to_100(self):
        with self.assertRaises(AdapterError):
            MetalSpendGovernor(
                Money(100, "USDZ"),
                (AgentBudget("a", 90, Money(1, "USDZ")),),
                FakeMetalTransport(),
            )


class EvaluatorTest(unittest.TestCase):
    def test_parse_invoice_text(self):
        parsed = parse_invoice_text("Invoice INV-1. Counterparty: Supplier-A. Total due USD 50.00.")
        self.assertEqual((parsed.currency, parsed.amount_cents, parsed.counterparty_id), ("USD", 5000, "supplier-a"))

    def test_matching_invoice_yields_proposal(self):
        intent = DeterministicEvaluator().propose_from_text(
            clean_snapshot(), "obl-1", "Counterparty: Supplier-A. Total USD 50.00."
        )
        self.assertEqual(intent.amount_cents, 5000)

    def test_mismatched_invoice_is_refused_with_reasons(self):
        with self.assertRaises(DomainError) as ctx:
            DeterministicEvaluator().propose_from_text(
                clean_snapshot(), "obl-1", "Counterparty: Supplier-A. Total USD 51.00."
            )
        self.assertIn("amount differs", str(ctx.exception))

    def test_unreadable_invoice_is_refused(self):
        with self.assertRaises(DomainError):
            parse_invoice_text("no amounts here")


if __name__ == "__main__":
    unittest.main()
