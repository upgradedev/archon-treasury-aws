"""Anonymous judge demo scenario: 5 obligations, 3 currencies, 72 hours.

Everything here is synthetic and runs on FakeAirwallexTransport. The demo
executes the real differentiator end to end: approve in one currency, land
a deposit in another, watch only the affected approvals fall, then execute
a still-valid approval through the Writer gate. No account, no credential.
Swap the fake transport for a live one after O-2; nothing else changes.
"""

import json
import threading
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone

from adapters.airwallex_client import AirwallexClient, FakeAirwallexTransport, parse_major_amount
from adapters.metal_client import AgentBudget, FakeMetalTransport, MetalSpendGovernor
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
from kerdon.money import Money
from kerdon.models import (
    Balance,
    ExecutionRecord,
    LedgerEntry,
    Obligation,
    ObligationStatus,
    PendingApproval,
    TreasurySnapshot,
)
from kerdon.ports import ExecutionGate, writer
from kerdon.receipts import build_receipt

DEMO_WEBHOOK_SECRET = "demo-only-secret-not-for-production"
APPROVER = "elena-vance"
ACCOUNT_BY_CURRENCY = {"USD": "ga-us-demo", "EUR": "ga-de-demo", "GBP": "ga-gb-demo"}


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
        # Two seeded gaps so the completeness panel is alive on first load:
        # an unbooked USD client deposit (R02) and a GBP bank debit with no
        # supplier invoice on file (R01). Ledger rows never move balances or
        # approval evidence in the snapshot model, so the hero story is safe.
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
            AgentBudget("agent-fx", 50, Money(25, "USDZ")),
            AgentBudget("agent-docs", 30, Money(10, "USDZ")),
            AgentBudget("agent-watch", 20, Money(5, "USDZ")),
        ),
        transport=FakeMetalTransport(),
    )


@dataclass(slots=True)
class DemoService:
    snapshot: TreasurySnapshot
    transport: FakeAirwallexTransport = field(default_factory=FakeAirwallexTransport)
    metal: MetalSpendGovernor = field(default_factory=_seed_metal)
    tokens: dict[str, ApprovalToken] = field(default_factory=dict)
    receipts: dict[str, dict] = field(default_factory=dict)
    transfers: dict[str, str] = field(default_factory=dict)
    _gate: ExecutionGate = field(default_factory=lambda: ExecutionGate(RequestIdLedger()))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @classmethod
    def seeded(cls, as_of: datetime | None = None) -> "DemoService":
        return cls(seed_snapshot(as_of or datetime.now(timezone.utc)))

    def reset(self) -> None:
        with self._lock:
            fresh = DemoService.seeded(self.snapshot.as_of)
            self.snapshot, self.transport, self.metal = fresh.snapshot, fresh.transport, fresh.metal
            self.tokens, self.receipts, self.transfers, self._gate = {}, {}, {}, fresh._gate

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

    def state(self) -> dict:
        with self._lock:
            return self._state_locked()

    def _state_locked(self) -> dict:
        rows = []
        for obl in sorted(self.snapshot.obligations, key=lambda o: o.obligation_id):
            token = self.tokens.get(obl.obligation_id)
            if obl.obligation_id in self.transfers:
                approval_state, reason = "PAID", f"Transfer {self.transfers[obl.obligation_id]} sent."
            elif token is None:
                approval_state, reason = "NOT_APPROVED", "Approve this payout to enable execution."
            else:
                result = check_token(token, self.snapshot)
                approval_state = result.state.value
                if result.state is ApprovalState.VALID:
                    reason = "Evidence unchanged. Safe to execute."
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
                    "amount": obl.amount.spoken(),
                    "due_at": obl.due_at.isoformat() if obl.due_at else None,
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
                    "amount": b.amount.spoken(),
                    "reserve_floor": Money(
                        self.snapshot.reserve_floor_cents(b.amount.currency), b.amount.currency
                    ).spoken(),
                }
                for b in sorted(self.snapshot.balances, key=lambda x: x.account_id)
            ],
            "obligations": rows,
            "findings": [
                {"rule_id": f.rule_id, "severity": f.severity.value, "subject_id": f.subject_id, "message": f.message}
                for f in evaluate(self.snapshot)
            ],
            "metal_agents": [
                {
                    "agent_id": b.agent_id,
                    "weight_percent": b.weight,
                    "allowance": Money(self.metal.allowance_cents(b.agent_id), "USDZ").spoken(),
                    "price_per_call": b.price_per_call.spoken(),
                    "call_cap": self.metal.call_cap(b.agent_id),
                    "calls_used": self.metal._calls.get(b.agent_id, 0),
                    "spent": Money(self.metal.spent_cents(b.agent_id), "USDZ").spoken(),
                }
                for b in self.metal.budgets
            ],
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
