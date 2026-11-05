"""Anonymous judge demo scenario: 5 obligations, 3 currencies, 72 hours.

Executes the full Kit 1 (Adaptive Treasury Controller), Kit 3 (Payment Ops
Incident Commander), and Kit 11 (Metal x402 Business Agents) flows end to end:
- Content-addressed SHA-256 approvals and selective invalidation on deposit
- 21 deterministic completeness rules (including live R01, R02, R09, R18)
- Forecast confidence policy (lowered by contradicting customer email)
- SWIFT EUR 12.85 vs LOCAL 0.00 fee calculation and triage plan
- Kit 3 stuck transfer SENT -> CANCELLED (bank_return) -> replacement lock
- Kit 11 Metal USDZ sub-agent spend caps and signed-order dispute refunds
- Evaluator invoice inspection (Amazon Bedrock Claude Haiku live when enabled,
  with deterministic fallback offline).
"""

import json
import os
import threading
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone

from adapters.airwallex_client import AirwallexClient, FakeAirwallexTransport, parse_major_amount
from adapters.bedrock_evaluator import BedrockEvaluator
from adapters.evaluator import DeterministicEvaluator
from adapters.metal_client import (
    AgentBudget,
    FakeMetalTransport,
    MetalSpendGovernor,
    SignedX402Order,
    sign_x402_order,
)
from adapters.webhook import handle_webhook, sign_payload
from kerdon.approvals import (
    ApprovalIntent,
    ApprovalState,
    ApprovalToken,
    RequestIdLedger,
    check_token,
    derive_request_id,
    operation_sha256,
)
from kerdon.completeness import evaluate
from kerdon.errors import DomainError, StaleApprovalError
from kerdon.models import (
    Balance,
    ExecutionRecord,
    LedgerEntry,
    Obligation,
    ObligationStatus,
    PendingApproval,
    TreasurySnapshot,
)
from kerdon.money import Money
from kerdon.planner import (
    PayoutRail,
    TransferIncident,
    TransferLifecycle,
    build_treasury_plan,
    evaluate_forecast_confidence,
    rail_fee_for,
    resolve_transfer_incident,
    transition_incident_to_cancelled,
)
from kerdon.ports import ExecutionGate, writer
from kerdon.receipts import build_receipt

DEMO_WEBHOOK_SECRET = "demo-only-secret-not-for-production"
APPROVER = "elena-vance"
ACCOUNT_BY_CURRENCY = {"USD": "ga-us-demo", "EUR": "ga-de-demo", "GBP": "ga-gb-demo"}

SUPPLIER_META = {
    "obl-usd-1": {
        "supplier_name": "Shenzhen Precision PCB Ltd.",
        "invoice_ref": "INV-2026-8841",
        "priority": "CRITICAL_OPS",
        "rail": PayoutRail.LOCAL,
        "summary": "High-density PCB boards; non-payment halts assembly line",
    },
    "obl-eur-1": {
        "supplier_name": "Munich Optics GmbH",
        "invoice_ref": "INV-2026-9104",
        "priority": "TIME_SENSITIVE",
        "rail": PayoutRail.SWIFT,
        "summary": "Precision sensor optics batch; international SWIFT wire",
    },
    "obl-eur-2": {
        "supplier_name": "Berlin CNC Tooling AG",
        "invoice_ref": "INV-2026-9150",
        "priority": "STANDARD",
        "rail": PayoutRail.LOCAL,
        "summary": "Aluminum enclosure jigs; SEPA Instant local rail",
    },
    "obl-gbp-1": {
        "supplier_name": "Thames Freight Logistics Ltd.",
        "invoice_ref": "INV-2026-4412",
        "priority": "TIME_SENSITIVE",
        "rail": PayoutRail.SWIFT,
        "summary": "UK customs clearance and air freight forwarding",
    },
    "obl-usd-2": {
        "supplier_name": "Austin Silicon Packaging Inc.",
        "invoice_ref": "INV-2026-8902",
        "priority": "DEFERRABLE",
        "rail": PayoutRail.LOCAL,
        "summary": "Q4 wafer reserve lot; deferrable when USD floor binds",
    },
}

_BEDROCK_CALLS = 0
_BEDROCK_MAX_CALLS = 30


def seed_snapshot(as_of: datetime) -> TreasurySnapshot:
    def obl(oid, cp, cents, cur, hours):
        return Obligation(oid, cp, Money(cents, cur), as_of + timedelta(hours=hours))

    return TreasurySnapshot(
        as_of=as_of,
        balances=(
            Balance("ga-us-demo", Money(2500_00, "USD")),
            Balance("ga-de-demo", Money(1800_00, "EUR")),
            Balance("ga-gb-demo", Money(900_00, "GBP")),
        ),
        obligations=(
            obl("obl-usd-1", "supplier-a", 450_00, "USD", 24),
            obl("obl-eur-1", "supplier-b", 800_00, "EUR", 48),
            obl("obl-eur-2", "supplier-c", 250_00, "EUR", 70),
            obl("obl-gbp-1", "supplier-d", 350_00, "GBP", 30),
            obl("obl-usd-2", "supplier-e", 1650_00, "USD", 72),
        ),
        ledger_entries=(
            LedgerEntry("led-usd-credit", "ga-us-demo", "client-x", Money(275_00, "USD"), as_of - timedelta(hours=2)),
            LedgerEntry("led-gbp-debit", "ga-gb-demo", "supplier-d", Money(-350_00, "GBP"), as_of - timedelta(hours=3)),
        ),
        reserve_floors=(Money(500_00, "USD"), Money(400_00, "EUR"), Money(300_00, "GBP")),
    )


def _seed_metal() -> MetalSpendGovernor:
    return MetalSpendGovernor(
        total_budget=Money(100_00, "USDZ"),
        budgets=(
            AgentBudget("agent-fx", 50, Money(25, "USDZ"), max_price_per_call_cents=35),
            AgentBudget("agent-docs", 30, Money(10, "USDZ"), max_price_per_call_cents=25),
            AgentBudget("agent-watch", 20, Money(5, "USDZ"), max_price_per_call_cents=20),
        ),
        transport=FakeMetalTransport(),
    )


def _seed_incident() -> TransferIncident:
    return TransferIncident(
        incident_id="inc-swift-8801",
        obligation_id="obl-eur-1",
        original_transfer_id="trn_swift_8801",
        original_request_id=derive_request_id("initial:trn_swift_8801"),
        amount=Money(800_00, "EUR"),
        rail=PayoutRail.SWIFT,
        status=TransferLifecycle.SENT,
    )


def _seed_disputed_orders() -> tuple[SignedX402Order, ...]:
    return (
        SignedX402Order(
            order_id="ord-x402-1",
            customer_id="cust-alpha-quant",
            resource="/v1/fx-tick-stream",
            price_cents=5,
            data_quality_ok=True,
            signature=sign_x402_order("ord-x402-1", "cust-alpha-quant", "/v1/fx-tick-stream", 5),
        ),
        SignedX402Order(
            order_id="ord-x402-2",
            customer_id="cust-alpha-quant",
            resource="/v1/fx-tick-stream",
            price_cents=5,
            data_quality_ok=False,
            signature=sign_x402_order("ord-x402-2", "cust-alpha-quant", "/v1/fx-tick-stream", 5),
        ),
        SignedX402Order(
            order_id="ord-x402-3",
            customer_id="cust-alpha-quant",
            resource="/v1/fx-tick-stream",
            price_cents=5,
            data_quality_ok=True,
            signature=sign_x402_order("ord-x402-3", "cust-alpha-quant", "/v1/fx-tick-stream", 5),
        ),
    )


@dataclass(slots=True)
class DemoService:
    snapshot: TreasurySnapshot
    transport: FakeAirwallexTransport = field(default_factory=FakeAirwallexTransport)
    metal: MetalSpendGovernor = field(default_factory=_seed_metal)
    incident: TransferIncident = field(default_factory=_seed_incident)
    tokens: dict[str, ApprovalToken] = field(default_factory=dict)
    receipts: dict[str, dict] = field(default_factory=dict)
    transfers: dict[str, str] = field(default_factory=dict)
    contradicted_by_email: bool = False
    deposit_confirmed: bool = False
    last_dispute_report: dict | None = None
    last_ai_inspection: dict | None = None
    _gate: ExecutionGate = field(default_factory=lambda: ExecutionGate(RequestIdLedger()))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @classmethod
    def seeded(cls, as_of: datetime | None = None) -> "DemoService":
        return cls(seed_snapshot(as_of or datetime.now(timezone.utc)))

    def reset(self) -> None:
        with self._lock:
            fresh = DemoService.seeded(self.snapshot.as_of)
            self.snapshot, self.transport, self.metal = fresh.snapshot, fresh.transport, fresh.metal
            self.incident = fresh.incident
            self.tokens, self.receipts, self.transfers, self._gate = {}, {}, {}, fresh._gate
            self.contradicted_by_email = False
            self.deposit_confirmed = False
            self.last_dispute_report = None
            self.last_ai_inspection = None

    def approve(self, obligation_id: str) -> dict:
        with self._lock:
            return self._approve_locked(obligation_id)

    def _approve_locked(self, obligation_id: str) -> dict:
        obl = self._obligation(obligation_id)
        token = ApprovalToken(
            ApprovalIntent.from_snapshot(self.snapshot, obl, "demo-terms-net-14"),
            APPROVER,
            self.snapshot.as_of,
        )
        self.tokens[obligation_id] = token
        kept = tuple(p for p in self.snapshot.pending_approvals if p.obligation_id != obligation_id)
        self.snapshot = replace(
            self.snapshot,
            pending_approvals=kept + (PendingApproval(obligation_id, token.sha256, token.intent.evidence_sha256),),
        )
        receipt = build_receipt(token, self.snapshot)
        self.receipts[obligation_id] = {
            "spoken_text": receipt.spoken_text,
            "braille_transcript": receipt.braille_transcript,
            "merkle_root_sha256": receipt.root_sha256,
            "merkle_verified": receipt.verify(),
        }
        return {"obligation_id": obligation_id, "approval_sha256": token.sha256, "state": "VALID"}

    def simulate_deposit(self, currency: str, amount_major: str) -> dict:
        with self._lock:
            return self._simulate_deposit_locked(currency, amount_major)

    def _simulate_deposit_locked(self, currency: str, amount_major: str) -> dict:
        money = parse_major_amount(amount_major, currency)
        if not money.is_positive:
            raise DomainError("deposit amount must be greater than zero")
        account = ACCOUNT_BY_CURRENCY.get(currency)
        if account is None:
            raise DomainError(f"no demo account for currency {currency!r}")
        body = json.dumps(
            {
                "id": f"evt-demo-{len(self.transport.calls) + 1}",
                "data": {"global_account_id": account, "currency": currency, "amount": money.to_major_str()},
            }
        ).encode()
        tokens = tuple(self.tokens.values())
        self.snapshot, results = handle_webhook(
            body, sign_payload(body, DEMO_WEBHOOK_SECRET), DEMO_WEBHOOK_SECRET, self.snapshot, tokens
        )
        self.deposit_confirmed = True
        self.contradicted_by_email = False
        return {
            "currency": currency,
            "amount": money.spoken(),
            "invalidated": sorted(
                r.token.intent.obligation_id for r in results if r.state is ApprovalState.INVALIDATED
            ),
            "still_valid": sorted(
                r.token.intent.obligation_id for r in results if r.state is ApprovalState.VALID
            ),
        }

    def execute(self, obligation_id: str, expected_sha256: str | None = None) -> dict:
        with self._lock:
            return self._execute_locked(obligation_id, expected_sha256)

    def _execute_locked(self, obligation_id: str, expected_sha256: str | None = None) -> dict:
        if obligation_id in self.transfers:
            raise DomainError(f"{obligation_id} is already paid; a second payment is refused")
        token = self.tokens.get(obligation_id)
        if token is None:
            raise DomainError(f"no approval exists for {obligation_id}; approve it first")
        if expected_sha256 is not None and token.sha256 != expected_sha256:
            raise StaleApprovalError(
                f"approval digest for {obligation_id} changed since it was displayed"
            )
        client = AirwallexClient(self.transport)
        transfer_id = self._gate.execute(writer("treasury-writer"), token, self.snapshot, client)
        self.transfers[obligation_id] = transfer_id
        self._settle(obligation_id, token)
        return {"obligation_id": obligation_id, "transfer_id": transfer_id, "state": "PAID"}

    def apply_customer_email(self, contradicts: bool = True) -> dict:
        """Kit 1: customer email contradicting receipt forecast lowers autonomous limit."""
        with self._lock:
            self.contradicted_by_email = bool(contradicts)
            if contradicts:
                self.deposit_confirmed = False
            fc = evaluate_forecast_confidence(self.contradicted_by_email, self.deposit_confirmed)
            return {
                "confidence_bps": fc.confidence_bps,
                "confidence_pct": fc.confidence_bps // 100,
                "autonomous_limit": Money(fc.autonomous_limit_cents, "USD").spoken(),
                "contradicted_by_email": fc.contradicted_by_email,
                "reason": fc.reason,
            }

    def inspect_invoice(self, obligation_id: str = "obl-usd-1", mode: str = "matching") -> dict:
        """Run Evaluator (live Bedrock when enabled, deterministic fallback) on invoice text."""
        global _BEDROCK_CALLS
        with self._lock:
            obl = self.snapshot.obligation(obligation_id)
            if obl is None:
                raise DomainError(f"unknown obligation {obligation_id!r}")
            meta = SUPPLIER_META.get(obligation_id, {})
            inv_amount = (
                obl.amount
                if mode == "matching"
                else Money(obl.amount.amount_cents + 45_00, obl.amount.currency)
            )
            invoice_text = (
                f"INVOICE {meta.get('invoice_ref', 'INV-DEMO-1')}\n"
                f"Supplier: {meta.get('supplier_name', obl.counterparty_id)}\n"
                f"Counterparty: {obl.counterparty_id}\n"
                f"Obligation: {obl.obligation_id}\n"
                f"Total due {inv_amount.currency} {inv_amount.to_major_str()}"
            )
            engine_used = "deterministic-evaluator-port"
            intent = None
            error_msg = None
            if os.environ.get("ARCHON_ENABLE_LIVE_BEDROCK") == "1" and _BEDROCK_CALLS < _BEDROCK_MAX_CALLS:
                try:
                    _BEDROCK_CALLS += 1
                    be = BedrockEvaluator()
                    intent = be.propose_from_text(self.snapshot, obligation_id, invoice_text)
                    engine_used = "amazon-bedrock-live (claude-haiku-4-5)"
                except DomainError as exc:
                    if "boto3" not in str(exc):
                        engine_used = "amazon-bedrock-live (deterministic-gate-refused)"
                        error_msg = str(exc)
                except Exception:
                    engine_used = "deterministic-evaluator-fallback"
            if intent is None and error_msg is None:
                de = DeterministicEvaluator()
                try:
                    intent = de.propose_from_text(self.snapshot, obligation_id, invoice_text)
                except DomainError as exc:
                    error_msg = str(exc)
            report = {
                "obligation_id": obligation_id,
                "mode": mode,
                "engine": engine_used,
                "invoice_preview": invoice_text,
                "verdict": "PROPOSED" if intent is not None else "REFUSED",
                "evidence_sha256": intent.evidence_sha256 if intent is not None else None,
                "reason": (
                    f"Invoice matches {obl.amount.spoken()} and counterparty {obl.counterparty_id}; typed ApprovalIntent proposed."
                    if intent is not None
                    else f"Evaluator gate refused invoice: {error_msg}"
                ),
            }
            self.last_ai_inspection = report
            return report

    def trigger_incident_failure(self, failure_type: str = "bank_return") -> dict:
        """Kit 3: transition SENT transfer to CANCELLED with a bank failure_type."""
        with self._lock:
            self.incident = transition_incident_to_cancelled(self.incident, failure_type)
            return self._incident_dict()

    def resolve_incident(self) -> dict:
        """Kit 3: issue replacement transfer under duplicate lock with fresh request_id."""
        with self._lock:
            repl_id = f"trn_repl_{len(self.transport.calls) + 1}"
            decision, updated = resolve_transfer_incident(self.incident, repl_id)
            self.incident = updated
            out = self._incident_dict()
            out["decision"] = decision.value
            return out

    def pay_metal_call(self, agent_id: str, memo: str = "x402-tool-call") -> dict:
        with self._lock:
            tx = self.metal.pay_for_call(agent_id, memo)
            return {
                "agent_id": agent_id,
                "tx_id": tx,
                "calls_used": self.metal._calls.get(agent_id, 0),
                "call_cap": self.metal.call_cap(agent_id),
                "spent": Money(self.metal.spent_cents(agent_id), "USDZ").spoken(),
            }

    def rebalance_metal(self, agent_id: str, new_price_major: str) -> dict:
        with self._lock:
            money = parse_major_amount(new_price_major, "USDZ")
            changes = self.metal.rebalance({agent_id: money})
            return {
                "agent_id": agent_id,
                "new_price": money.spoken(),
                "changes": list(changes),
            }

    def replace_metal_mandate(self, agent_id: str, new_max_price_cents: int) -> dict:
        with self._lock:
            return self.metal.replace_mandate(agent_id, new_max_price_cents)

    def resolve_metal_dispute(self) -> dict:
        with self._lock:
            report = self.metal.resolve_disputed_batch("agent-docs", _seed_disputed_orders())
            self.last_dispute_report = report
            return report

    def state(self) -> dict:
        with self._lock:
            return self._state_locked()

    def _incident_dict(self) -> dict:
        inc = self.incident
        return {
            "incident_id": inc.incident_id,
            "obligation_id": inc.obligation_id,
            "original_transfer_id": inc.original_transfer_id,
            "original_request_id": inc.original_request_id,
            "amount": inc.amount.spoken(),
            "rail": inc.rail.value,
            "status": inc.status.value,
            "failure_type": inc.failure_type,
            "replacement_transfer_id": inc.replacement_transfer_id,
            "replacement_request_id": inc.replacement_request_id,
            "swift_fees_budgeted": Money(inc.swift_fees_budgeted_cents, "EUR").spoken(),
        }

    def _state_locked(self) -> dict:
        fc = evaluate_forecast_confidence(self.contradicted_by_email, self.deposit_confirmed)
        rails = {oid: meta["rail"] for oid, meta in SUPPLIER_META.items()}
        priorities = {oid: meta["priority"] for oid, meta in SUPPLIER_META.items()}
        plan_by_id = {
            row.obligation_id: row
            for row in build_treasury_plan(self.snapshot, rails, priorities, fc)
        }

        rows = []
        for obl in sorted(self.snapshot.obligations, key=lambda o: o.obligation_id):
            token = self.tokens.get(obl.obligation_id)
            meta = SUPPLIER_META.get(obl.obligation_id, {})
            plan_row = plan_by_id.get(obl.obligation_id)
            rail = meta.get("rail", PayoutRail.LOCAL)
            fee = rail_fee_for(rail)
            if obl.obligation_id in self.transfers:
                approval_state, reason = "PAID", f"Transfer {self.transfers[obl.obligation_id]} settled."
            elif token is None:
                approval_state, reason = "NOT_APPROVED", "Approve this payout to bind current balance and FX evidence."
            else:
                result = check_token(token, self.snapshot)
                approval_state = result.state.value
                if result.state is ApprovalState.VALID:
                    reason = "Evidence digest verified. Ready for Writer gate execution."
                elif "reserve-floor-breach" in result.reasons:
                    reason = (
                        f"Execution blocked: {', '.join(result.reasons)}. "
                        "Land a deposit to restore the reserve floor, then re-approve."
                    )
                else:
                    reason = f"Execution blocked: {', '.join(result.reasons)}. Re-approve on current evidence."
            rows.append(
                {
                    "obligation_id": obl.obligation_id,
                    "counterparty_id": obl.counterparty_id,
                    "supplier_name": meta.get("supplier_name", obl.counterparty_id),
                    "invoice_ref": meta.get("invoice_ref", "INV-DEMO"),
                    "priority": meta.get("priority", "STANDARD"),
                    "rail": rail.value,
                    "rail_fee": fee.spoken(),
                    "summary": meta.get("summary", ""),
                    "amount": obl.amount.spoken(),
                    "amount_major": f"{obl.amount.currency} {obl.amount.to_major_str()}",
                    "due_at": obl.due_at.isoformat() if obl.due_at else None,
                    "plan_action": plan_row.action.value if plan_row else "FUND_NOW",
                    "plan_rationale": plan_row.rationale if plan_row else "",
                    "requires_human_approval": plan_row.requires_human_approval if plan_row else True,
                    "approval_state": approval_state,
                    "approval_sha256": token.sha256 if token else None,
                    "action_reason": reason,
                    "receipt": self.receipts.get(obl.obligation_id),
                }
            )
        return {
            "balances": [
                {
                    "account_id": b.account_id,
                    "currency": b.amount.currency,
                    "amount": b.amount.spoken(),
                    "amount_major": f"{b.amount.currency} {b.amount.to_major_str()}",
                    "amount_cents": b.amount.amount_cents,
                    "reserve_floor": Money(
                        self.snapshot.reserve_floor_cents(b.amount.currency), b.amount.currency
                    ).spoken(),
                    "reserve_floor_major": (
                        f"{b.amount.currency} "
                        f"{Money(self.snapshot.reserve_floor_cents(b.amount.currency), b.amount.currency).to_major_str()}"
                    ),
                    "reserve_floor_cents": self.snapshot.reserve_floor_cents(b.amount.currency),
                    "headroom_major": (
                        f"{b.amount.currency} "
                        f"{Money(max(0, b.amount.amount_cents - self.snapshot.reserve_floor_cents(b.amount.currency)), b.amount.currency).to_major_str()}"
                    ),
                }
                for b in sorted(self.snapshot.balances, key=lambda x: x.account_id)
            ],
            "forecast": {
                "confidence_bps": fc.confidence_bps,
                "confidence_pct": fc.confidence_bps // 100,
                "autonomous_limit": Money(fc.autonomous_limit_cents, "USD").spoken(),
                "autonomous_limit_major": f"USD {Money(fc.autonomous_limit_cents, 'USD').to_major_str()}",
                "contradicted_by_email": fc.contradicted_by_email,
                "reason": fc.reason,
            },
            "obligations": rows,
            "findings": [
                {"rule_id": f.rule_id, "severity": f.severity.value, "subject_id": f.subject_id, "message": f.message}
                for f in evaluate(self.snapshot)
            ],
            "incident": self._incident_dict(),
            "metal_agents": [
                {
                    "agent_id": b.agent_id,
                    "weight_percent": b.weight,
                    "allowance": Money(self.metal.allowance_cents(b.agent_id), "USDZ").spoken(),
                    "allowance_major": f"USDZ {Money(self.metal.allowance_cents(b.agent_id), 'USDZ').to_major_str()}",
                    "price_per_call": b.price_per_call.spoken(),
                    "price_major": f"USDZ {b.price_per_call.to_major_str()}",
                    "max_price_per_call_cents": b.max_price_per_call_cents,
                    "call_cap": self.metal.call_cap(b.agent_id),
                    "calls_used": self.metal._calls.get(b.agent_id, 0),
                    "spent": Money(self.metal.spent_cents(b.agent_id), "USDZ").spoken(),
                }
                for b in self.metal.budgets
            ],
            "last_dispute_report": self.last_dispute_report,
            "last_ai_inspection": self.last_ai_inspection,
            "transfer_count": self.transport.transfer_count,
            "mode": "synthetic-demo-fake-transport",
        }

    def _obligation(self, obligation_id: str) -> Obligation:
        obl = self.snapshot.obligation(obligation_id)
        if obl is None:
            raise DomainError(f"unknown obligation {obligation_id!r}")
        if obligation_id in self.transfers:
            raise DomainError(f"{obligation_id} is already paid")
        return obl

    def _settle(self, obligation_id: str, token: ApprovalToken) -> None:
        balances = []
        for b in self.snapshot.balances:
            if b.amount.currency == token.intent.currency and b.account_id == ACCOUNT_BY_CURRENCY[token.intent.currency]:
                balances.append(Balance(b.account_id, Money(b.amount.amount_cents - token.intent.amount_cents, b.amount.currency)))
            else:
                balances.append(b)
        obligations = tuple(
            replace(o, status=ObligationStatus.PAID) if o.obligation_id == obligation_id else o
            for o in self.snapshot.obligations
        )
        op_sha = operation_sha256(token)
        exe = ExecutionRecord(
            execution_id=f"exe-{len(self.snapshot.executions) + 1}",
            obligation_id=obligation_id,
            request_id=derive_request_id(op_sha),
            operation_sha256=op_sha,
            approval_sha256=token.sha256,
            executed_at=self.snapshot.as_of,
        )
        self.snapshot = replace(
            self.snapshot,
            balances=tuple(balances),
            obligations=obligations,
            executions=self.snapshot.executions + (exe,),
        )
