"""Deterministic Treasury Planner (Kit 1 Adaptive Treasury Controller and
Kit 3 Payment Ops Incident Commander).

All policy thresholds, SWIFT fees, forecast confidence limits, and replacement
transfer locks live in deterministic integer-cents code. Models may parse
unstructured emails or invoices upstream, but only this module decides which
obligations to fund, convert, defer, or escalate, and how to recover a failed
transfer without paying twice.
"""

from dataclasses import dataclass
from enum import Enum

from kerdon.approvals import derive_request_id
from kerdon.errors import DomainError, DuplicateRequestIdError
from kerdon.models import Obligation, ObligationStatus, TreasurySnapshot
from kerdon.money import Money

SWIFT_FEE_EUR_CENTS = 12_85
HIGH_CONFIDENCE_THRESHOLD_BPS = 8000
HIGH_CONFIDENCE_AUTO_LIMIT_CENTS = 2500_00
LOW_CONFIDENCE_AUTO_LIMIT_CENTS = 0


class PlanAction(str, Enum):
    FUND_NOW = "FUND_NOW"
    CONVERT_FX = "CONVERT_FX"
    DEFER = "DEFER"
    ESCALATE = "ESCALATE"
    SETTLED = "SETTLED"


class PayoutRail(str, Enum):
    LOCAL = "LOCAL"
    SWIFT = "SWIFT"


class TransferLifecycle(str, Enum):
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class IncidentDecision(str, Enum):
    WAIT = "WAIT"
    REPLACE = "REPLACE"
    ESCALATE = "ESCALATE"
    RESOLVED = "RESOLVED"


@dataclass(frozen=True)
class ForecastState:
    confidence_bps: int
    autonomous_limit_cents: int
    reason: str
    contradicted_by_email: bool


@dataclass(frozen=True)
class ObligationPlanRow:
    obligation_id: str
    action: PlanAction
    rail: PayoutRail
    fee_cents: int
    fee_currency: str
    requires_human_approval: bool
    rationale: str


@dataclass(frozen=True)
class TransferIncident:
    incident_id: str
    obligation_id: str
    original_transfer_id: str
    original_request_id: str
    amount: Money
    rail: PayoutRail
    status: TransferLifecycle
    failure_type: str | None = None
    replacement_transfer_id: str | None = None
    replacement_request_id: str | None = None
    swift_fees_budgeted_cents: int = SWIFT_FEE_EUR_CENTS


def evaluate_forecast_confidence(
    contradicted_by_email: bool,
    deposit_confirmed: bool = False,
) -> ForecastState:
    """Kit 1 policy: tie autonomous execution limit to forecast confidence."""
    if deposit_confirmed:
        return ForecastState(
            confidence_bps=9800,
            autonomous_limit_cents=HIGH_CONFIDENCE_AUTO_LIMIT_CENTS,
            reason="Incoming deposit webhook settled; receipt forecast verified in bank ledger.",
            contradicted_by_email=False,
        )
    if contradicted_by_email:
        return ForecastState(
            confidence_bps=3500,
            autonomous_limit_cents=LOW_CONFIDENCE_AUTO_LIMIT_CENTS,
            reason="Customer email contradicts receipt forecast; autonomous limit lowered to zero.",
            contradicted_by_email=True,
        )
    return ForecastState(
        confidence_bps=9200,
        autonomous_limit_cents=HIGH_CONFIDENCE_AUTO_LIMIT_CENTS,
        reason="Bank history and signed PO support receipt forecast; standard autonomous limit active.",
        contradicted_by_email=False,
    )


def rail_fee_for(rail: PayoutRail) -> Money:
    """Kit 1 rule: include flat EUR 12.85 fee for SWIFT; LOCAL has no fee."""
    if rail is PayoutRail.SWIFT:
        return Money(SWIFT_FEE_EUR_CENTS, "EUR")
    return Money(0, "EUR")


def _has_matching_document(snapshot: TreasurySnapshot, ob: Obligation) -> bool:
    for doc in snapshot.documents:
        if doc.obligation_id == ob.obligation_id:
            return (
                doc.amount.currency == ob.amount.currency
                and doc.amount.amount_cents == ob.amount.amount_cents
                and doc.counterparty_id == ob.counterparty_id
            )
    return True


def build_treasury_plan(
    snapshot: TreasurySnapshot,
    rails: dict[str, PayoutRail],
    priorities: dict[str, str],
    forecast: ForecastState,
) -> tuple[ObligationPlanRow, ...]:
    """Classify every obligation into FUND_NOW, CONVERT_FX, DEFER, or ESCALATE."""
    rows: list[ObligationPlanRow] = []
    running_available: dict[str, int] = {}
    for bal in snapshot.balances:
        floor = snapshot.reserve_floor_cents(bal.amount.currency)
        running_available[bal.amount.currency] = bal.amount.amount_cents - floor

    for ob in snapshot.obligations:
        rail = rails.get(ob.obligation_id, PayoutRail.LOCAL)
        fee = rail_fee_for(rail)
        priority = priorities.get(ob.obligation_id, "STANDARD")

        if ob.status is ObligationStatus.PAID:
            rows.append(
                ObligationPlanRow(
                    obligation_id=ob.obligation_id,
                    action=PlanAction.SETTLED,
                    rail=rail,
                    fee_cents=fee.amount_cents,
                    fee_currency=fee.currency,
                    requires_human_approval=False,
                    rationale="Payout already settled through the Writer gate.",
                )
            )
            continue

        if not _has_matching_document(snapshot, ob):
            rows.append(
                ObligationPlanRow(
                    obligation_id=ob.obligation_id,
                    action=PlanAction.ESCALATE,
                    rail=rail,
                    fee_cents=fee.amount_cents,
                    fee_currency=fee.currency,
                    requires_human_approval=True,
                    rationale="Policy exception: invoice evidence differs from obligation terms.",
                )
            )
            continue

        headroom = running_available.get(ob.amount.currency, 0)
        needs_human = (
            ob.amount.amount_cents > forecast.autonomous_limit_cents
            or forecast.contradicted_by_email
        )

        if headroom >= ob.amount.amount_cents:
            running_available[ob.amount.currency] = headroom - ob.amount.amount_cents
            rows.append(
                ObligationPlanRow(
                    obligation_id=ob.obligation_id,
                    action=PlanAction.FUND_NOW,
                    rail=rail,
                    fee_cents=fee.amount_cents,
                    fee_currency=fee.currency,
                    requires_human_approval=needs_human,
                    rationale=(
                        f"{priority}: funded from available {ob.amount.currency} above reserve floor"
                        + (" (human approval required by forecast policy)." if needs_human else ".")
                    ),
                )
            )
        elif priority in ("CRITICAL_OPS", "TIME_SENSITIVE"):
            shortfall = ob.amount.amount_cents - max(0, headroom)
            swift_note = (
                f" plus EUR 12.85 ({SWIFT_FEE_EUR_CENTS} cents) SWIFT fee"
                if rail is PayoutRail.SWIFT
                else " on LOCAL rail (0 fee)"
            )
            rows.append(
                ObligationPlanRow(
                    obligation_id=ob.obligation_id,
                    action=PlanAction.CONVERT_FX,
                    rail=rail,
                    fee_cents=fee.amount_cents,
                    fee_currency=fee.currency,
                    requires_human_approval=True,
                    rationale=(
                        f"{priority}: convert minimum {ob.amount.currency} shortfall "
                        f"({shortfall} cents){swift_note} to preserve reserve floor."
                    ),
                )
            )
        else:
            rows.append(
                ObligationPlanRow(
                    obligation_id=ob.obligation_id,
                    action=PlanAction.DEFER,
                    rail=rail,
                    fee_cents=fee.amount_cents,
                    fee_currency=fee.currency,
                    requires_human_approval=True,
                    rationale=(
                        f"Defer lower-priority payout: executing {ob.amount.spoken()} "
                        f"would breach the {ob.amount.currency} reserve floor."
                    ),
                )
            )
    return tuple(rows)


def transition_incident_to_cancelled(
    incident: TransferIncident,
    failure_type: str,
) -> TransferIncident:
    """Kit 3 rule: failure_type applies only after the transfer reaches SENT."""
    if incident.status is not TransferLifecycle.SENT:
        raise DomainError("transfer must reach SENT before a failure_type transition applies")
    if not failure_type or not failure_type.strip():
        raise DomainError("failure_type is required for CANCELLED transition")
    return TransferIncident(
        incident_id=incident.incident_id,
        obligation_id=incident.obligation_id,
        original_transfer_id=incident.original_transfer_id,
        original_request_id=incident.original_request_id,
        amount=incident.amount,
        rail=incident.rail,
        status=TransferLifecycle.CANCELLED,
        failure_type=failure_type.strip(),
        replacement_transfer_id=incident.replacement_transfer_id,
        replacement_request_id=incident.replacement_request_id,
        swift_fees_budgeted_cents=incident.swift_fees_budgeted_cents,
    )


def resolve_transfer_incident(
    incident: TransferIncident,
    replacement_transfer_id: str,
) -> tuple[IncidentDecision, TransferIncident]:
    """Kit 3 Incident Commander: decide WAIT, REPLACE, or ESCALATE under a duplicate lock."""
    if incident.replacement_transfer_id is not None:
        raise DuplicateRequestIdError(
            f"incident {incident.incident_id} already issued replacement {incident.replacement_transfer_id}"
        )
    if incident.status in (TransferLifecycle.PROCESSING, TransferLifecycle.SENT):
        return IncidentDecision.WAIT, incident
    if incident.status is TransferLifecycle.PAID:
        return IncidentDecision.RESOLVED, incident
    if incident.failure_type in ("bank_return", "account_closed_or_invalid", "recall"):
        op_hash = f"replace:{incident.incident_id}:{incident.original_transfer_id}:{incident.failure_type}"
        new_req_id = derive_request_id(op_hash)
        if new_req_id == incident.original_request_id:
            raise DuplicateRequestIdError("replacement request_id must differ from original")
        two_fees = (
            SWIFT_FEE_EUR_CENTS * 2
            if incident.rail is PayoutRail.SWIFT
            else 0
        )
        updated = TransferIncident(
            incident_id=incident.incident_id,
            obligation_id=incident.obligation_id,
            original_transfer_id=incident.original_transfer_id,
            original_request_id=incident.original_request_id,
            amount=incident.amount,
            rail=incident.rail,
            status=TransferLifecycle.CANCELLED,
            failure_type=incident.failure_type,
            replacement_transfer_id=replacement_transfer_id,
            replacement_request_id=new_req_id,
            swift_fees_budgeted_cents=two_fees,
        )
        return IncidentDecision.REPLACE, updated
    return IncidentDecision.ESCALATE, incident
