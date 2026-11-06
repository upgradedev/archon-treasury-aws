"""Metal USDZ caps under price moves, and the Evaluator proposal contract."""

import unittest

from adapters.airwallex_client import AdapterError
from adapters.evaluator import DeterministicEvaluator, parse_invoice_text
from adapters.metal_client import (
    AgentBudget,
    FakeMetalTransport,
    MetalSpendGovernor,
    SignedX402Order,
    sign_x402_order,
)
from fixtures import clean_snapshot
from kerdon.errors import DomainError, DuplicateRequestIdError
from kerdon.models import DocKind, DocumentEvidence
from kerdon.money import Money
from kerdon.planner import (
    CardMandateStatus,
    IncidentDecision,
    PayoutRail,
    PlanAction,
    TransferIncident,
    TransferLifecycle,
    VirtualCardMandate,
    authorize_virtual_card_charge,
    build_treasury_plan,
    evaluate_forecast_confidence,
    issue_virtual_visa_card,
    rail_fee_for,
    resolve_transfer_incident,
    transition_incident_to_cancelled,
)


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

    def test_mandate_per_call_cap_and_replacement(self):
        g = MetalSpendGovernor(
            Money(100_00, "USDZ"),
            (AgentBudget("sourcing", 100, Money(4, "USDZ"), max_price_per_call_cents=3),),
            FakeMetalTransport(),
        )
        with self.assertRaises(AdapterError):
            g.pay_for_call("sourcing", "upstream-query")
        g.replace_mandate("sourcing", 5)
        self.assertEqual(g.pay_for_call("sourcing", "upstream-query"), "mtl_fake_1")
        with self.assertRaises(AdapterError):
            g.replace_mandate("sourcing", 0)
        with self.assertRaises(AdapterError):
            g.replace_mandate("unknown", 5)

    def test_resolve_disputed_batch_verifies_signatures_and_refunds_faulty(self):
        g = governor()
        orders = (
            SignedX402Order("o-1", "c-1", "/r", 5, True, sign_x402_order("o-1", "c-1", "/r", 5)),
            SignedX402Order("o-2", "c-1", "/r", 5, False, sign_x402_order("o-2", "c-1", "/r", 5)),
            SignedX402Order("o-3", "c-1", "/r", 5, False, "bad-sig"),
        )
        res = g.resolve_disputed_batch("agent-docs", orders)
        self.assertEqual(res["refunded_cents"], 5)
        decisions = [v["decision"] for v in res["verdicts"]]
        self.assertEqual(decisions, ["DENY_REFUND_VALID_DELIVERY", "REFUNDED_FAULTY_DATA", "REJECT_UNSIGNED"])
        with self.assertRaises(AdapterError):
            g.resolve_disputed_batch("agent-docs", orders)  # duplicate refund refused


class PlannerAndIncidentTest(unittest.TestCase):
    def test_forecast_confidence_and_swift_fees(self):
        fc_std = evaluate_forecast_confidence(False, False)
        self.assertEqual(fc_std.confidence_bps, 9200)
        fc_low = evaluate_forecast_confidence(True, False)
        self.assertEqual(fc_low.autonomous_limit_cents, 0)
        fc_dep = evaluate_forecast_confidence(False, True)
        self.assertEqual(fc_dep.confidence_bps, 9800)
        self.assertEqual(rail_fee_for(PayoutRail.SWIFT).amount_cents, 1285)
        self.assertEqual(rail_fee_for(PayoutRail.LOCAL).amount_cents, 0)

    def test_build_treasury_plan_classifies_obligations(self):
        snap = clean_snapshot()
        fc = evaluate_forecast_confidence(False, False)
        plan = build_treasury_plan(snap, {"obl-1": PayoutRail.SWIFT}, {"obl-1": "CRITICAL_OPS"}, fc)
        self.assertEqual(plan[0].action, PlanAction.FUND_NOW)
        self.assertEqual(plan[0].fee_cents, 1285)
        bad_doc = DocumentEvidence("d-bad", DocKind.INVOICE, "supplier-a", Money(999_00, "USD"), "h", "INV-X", "obl-1")
        snap_bad = snap.__class__(
            as_of=snap.as_of,
            balances=snap.balances,
            obligations=snap.obligations,
            documents=(bad_doc,),
            reserve_floors=snap.reserve_floors,
        )
        plan_bad = build_treasury_plan(snap_bad, {}, {}, fc)
        self.assertEqual(plan_bad[0].action, PlanAction.ESCALATE)

    def test_incident_state_machine_and_duplicate_lock(self):
        inc = TransferIncident(
            "inc-1", "obl-1", "trn-1", "req-1", Money(800_00, "EUR"), PayoutRail.SWIFT, TransferLifecycle.SENT
        )
        decision_wait, _ = resolve_transfer_incident(inc, "trn-repl")
        self.assertEqual(decision_wait, IncidentDecision.WAIT)
        cancelled = transition_incident_to_cancelled(inc, "bank_return")
        decision_rep, updated = resolve_transfer_incident(cancelled, "trn-repl-1")
        self.assertEqual(decision_rep, IncidentDecision.REPLACE)
        self.assertEqual(updated.replacement_transfer_id, "trn-repl-1")
        self.assertEqual(updated.swift_fees_budgeted_cents, 2570)
        with self.assertRaises(DuplicateRequestIdError):
            resolve_transfer_incident(updated, "trn-repl-2")
        with self.assertRaises(DomainError):
            transition_incident_to_cancelled(cancelled, "bank_return")

    def test_kit9_virtual_visa_card_mcc_cap_and_single_use(self):
        mandate = VirtualCardMandate(
            card_id="visa-vc-1",
            obligation_id="obl-usd-1",
            supplier_name="Shenzhen Precision PCB Ltd.",
            limit=Money(450_00, "USD"),
            allowed_mcc="5045",
        )
        with self.assertRaises(DomainError):
            authorize_virtual_card_charge(mandate, 450_00, "5045")
        active = issue_virtual_visa_card(mandate)
        self.assertEqual(active.status, CardMandateStatus.ACTIVE)
        wrong_mcc = authorize_virtual_card_charge(active, 450_00, "5812")
        self.assertEqual(wrong_mcc.last_verdict, "DECLINED_MCC_MISMATCH")
        over_cap = authorize_virtual_card_charge(active, 460_00, "5045")
        self.assertEqual(over_cap.last_verdict, "DECLINED_OVER_LIMIT")
        approved = authorize_virtual_card_charge(active, 450_00, "5045")
        self.assertEqual(approved.status, CardMandateStatus.USED)
        self.assertEqual(approved.last_verdict, "APPROVED_SINGLE_USE")
        self.assertEqual(approved.rebate_earned_cents, 675)
        reused = authorize_virtual_card_charge(approved, 100_00, "5045")
        self.assertEqual(reused.last_verdict, "DECLINED_SINGLE_USE_EXHAUSTED")


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
