"""Changed-evidence approval invalidation and idempotent execution keys.

Contract (STATE.md section 4): every approval binds amount_cents, currency,
counterparty_id, fx_quote_id, terms_hash, and evidence_sha256. When new
evidence arrives (for example a deposit webhook), each pending approval is
re-checked on its own. Only approvals whose bound evidence changed are
invalidated; unaffected approvals stay valid. Execution is fail-closed:
a stale digest or a reserve-floor breach refuses the write.

Trap T3 (TRAPS.md): request_id values are derived as
uuid5(NAMESPACE, canonical_operation_hash). A retry of the exact same
operation reuses the UUID. A revised decision hashes differently and gets
a fresh UUID. Reusing one UUID for a different payload inside 7 days is
refused. Lock convention: age < 7 days is locked; age >= 7 days is expired.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from kerdon.errors import DuplicateRequestIdError, ReserveFloorError, StaleApprovalError
from kerdon.models import Obligation, TreasurySnapshot

REQUEST_ID_NAMESPACE = uuid.UUID("7a3f1c2e-4b5d-4e6f-8a90-1b2c3d4e5f60")
REQUEST_ID_LOCK = timedelta(days=7)


def canonical_json(payload: dict) -> str:
    """One canonical encoding for every digest in this package."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def evidence_payload(snapshot: TreasurySnapshot, obligation: Obligation) -> dict:
    """The exact evidence one approval depends on. Nothing else can stale it."""
    quote = snapshot.fx_quote(obligation.fx_quote_id)
    docs = sorted(
        d.content_sha256 for d in snapshot.documents if d.counterparty_id == obligation.counterparty_id
    )
    return {
        "obligation_id": obligation.obligation_id,
        "amount_cents": obligation.amount.amount_cents,
        "currency": obligation.amount.currency,
        "counterparty_id": obligation.counterparty_id,
        "balance_cents": snapshot.balance_cents(obligation.amount.currency),
        "reserve_floor_cents": snapshot.reserve_floor_cents(obligation.amount.currency),
        "fx_quote": None
        if quote is None
        else {
            "quote_id": quote.quote_id,
            "rate_numerator": quote.rate_numerator,
            "rate_denominator": quote.rate_denominator,
            "expires_at": quote.expires_at.isoformat(),
        },
        "document_sha256": docs,
    }


def evidence_sha256_for(snapshot: TreasurySnapshot, obligation: Obligation) -> str:
    return sha256_text(canonical_json(evidence_payload(snapshot, obligation)))


@dataclass(frozen=True, slots=True)
class ApprovalIntent:
    obligation_id: str
    amount_cents: int
    currency: str
    counterparty_id: str
    fx_quote_id: str | None
    terms_sha256: str
    evidence_sha256: str

    @classmethod
    def from_snapshot(
        cls, snapshot: TreasurySnapshot, obligation: Obligation, terms_text: str
    ) -> "ApprovalIntent":
        return cls(
            obligation_id=obligation.obligation_id,
            amount_cents=obligation.amount.amount_cents,
            currency=obligation.amount.currency,
            counterparty_id=obligation.counterparty_id,
            fx_quote_id=obligation.fx_quote_id,
            terms_sha256=sha256_text(terms_text),
            evidence_sha256=evidence_sha256_for(snapshot, obligation),
        )

    def payload(self) -> dict:
        return {
            "obligation_id": self.obligation_id,
            "amount_cents": self.amount_cents,
            "currency": self.currency,
            "counterparty_id": self.counterparty_id,
            "fx_quote_id": self.fx_quote_id,
            "terms_sha256": self.terms_sha256,
            "evidence_sha256": self.evidence_sha256,
        }

    @property
    def sha256(self) -> str:
        return sha256_text(canonical_json(self.payload()))


@dataclass(frozen=True, slots=True)
class ApprovalToken:
    intent: ApprovalIntent
    approver_id: str
    approved_at: datetime

    @property
    def sha256(self) -> str:
        return self.intent.sha256


class ApprovalState(Enum):
    VALID = "VALID"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True, slots=True)
class InvalidationResult:
    token: ApprovalToken
    state: ApprovalState
    reasons: tuple[str, ...] = ()


def reserve_after_cents(snapshot: TreasurySnapshot, intent: ApprovalIntent) -> int:
    return snapshot.balance_cents(intent.currency) - intent.amount_cents


def check_token(token: ApprovalToken, snapshot: TreasurySnapshot) -> InvalidationResult:
    """Re-check one approval against current evidence. Pure and total."""
    obligation = snapshot.obligation(token.intent.obligation_id)
    if obligation is None:
        return InvalidationResult(token, ApprovalState.INVALIDATED, ("obligation-missing",))
    reasons: list[str] = []
    if evidence_sha256_for(snapshot, obligation) != token.intent.evidence_sha256:
        reasons.append("evidence-changed")
    if (
        obligation.amount.amount_cents != token.intent.amount_cents
        or obligation.amount.currency != token.intent.currency
        or obligation.counterparty_id != token.intent.counterparty_id
        or obligation.fx_quote_id != token.intent.fx_quote_id
    ):
        reasons.append("obligation-changed")
    quote = snapshot.fx_quote(token.intent.fx_quote_id)
    if token.intent.fx_quote_id is not None and quote is not None and quote.expires_at <= snapshot.as_of:
        reasons.append("fx-quote-expired")
    floor = snapshot.reserve_floor_cents(token.intent.currency)
    if reserve_after_cents(snapshot, token.intent) < floor:
        reasons.append("reserve-floor-breach")
    state = ApprovalState.INVALIDATED if reasons else ApprovalState.VALID
    return InvalidationResult(token, state, tuple(reasons))


def invalidate_changed(
    tokens: tuple[ApprovalToken, ...], snapshot: TreasurySnapshot
) -> tuple[InvalidationResult, ...]:
    """Invalidate only the approvals whose bound evidence changed."""
    return tuple(check_token(t, snapshot) for t in sorted(tokens, key=lambda t: t.sha256))


def operation_sha256(token: ApprovalToken) -> str:
    return token.sha256


def derive_request_id(op_sha256: str) -> str:
    return str(uuid.uuid5(REQUEST_ID_NAMESPACE, f"kerdon:{op_sha256}"))


@dataclass(slots=True)
class RequestIdLedger:
    """In-memory 7-day request_id lock. Adapters persist the same contract."""

    _seen: dict[str, tuple[str, datetime]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._seen is None:
            self._seen = {}

    def register(self, request_id: str, op_sha256: str, now: datetime) -> None:
        prior = self._seen.get(request_id)
        if prior is not None:
            prior_op, first_seen = prior
            if now - first_seen < REQUEST_ID_LOCK:
                if prior_op != op_sha256:
                    raise DuplicateRequestIdError(
                        f"request_id {request_id} already bound to a different payload"
                    )
                return  # exact retry of the same operation: allowed, no double-pay
        self._seen[request_id] = (op_sha256, now)


def verify_for_execution(
    token: ApprovalToken, snapshot: TreasurySnapshot, ledger: RequestIdLedger
) -> str:
    """Writer gate. Returns the request_id to execute with, or refuses."""
    result = check_token(token, snapshot)
    if result.state is ApprovalState.INVALIDATED:
        if "reserve-floor-breach" in result.reasons and len(result.reasons) == 1:
            raise ReserveFloorError(
                f"execution would breach the {token.intent.currency} reserve floor"
            )
        raise StaleApprovalError(
            f"approval {token.sha256} is stale: {', '.join(result.reasons)}"
        )
    op = operation_sha256(token)
    request_id = derive_request_id(op)
    ledger.register(request_id, op, snapshot.as_of)
    return request_id
