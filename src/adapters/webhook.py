"""Airwallex deposit webhook: verify, apply, invalidate only what changed.

Flow (STATE.md section 1 autonomous trigger): an HMAC-signed deposit event
lands, the balance moves in a new snapshot, and the pure core re-checks
every pending approval. Approvals whose bound evidence did not change stay
valid. A bad signature refuses the whole event before any parsing trust.
"""

import hashlib
import hmac
import json
from dataclasses import dataclass, replace

from adapters.airwallex_client import AdapterError, parse_major_amount
from kerdon.approvals import ApprovalToken, InvalidationResult, invalidate_changed
from kerdon.money import Money
from kerdon.models import Balance, TreasurySnapshot


class SignatureError(AdapterError):
    """Webhook HMAC verification failed. The event is refused whole."""


class DuplicateWebhookError(AdapterError):
    """Webhook event_id has already been processed (replay protection)."""


def sign_payload(raw_body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def verify_signature(raw_body: bytes, signature: str | None, secret: str) -> bool:
    if not signature or not secret:
        return False
    return hmac.compare_digest(sign_payload(raw_body, secret), signature.strip().lower())


@dataclass(frozen=True, slots=True)
class DepositEvent:
    event_id: str
    account_id: str
    amount: Money


def parse_deposit_event(payload: dict) -> DepositEvent:
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        raise AdapterError("webhook payload data must be an object")
    try:
        account_id = str(data["global_account_id"])
        currency = str(data["currency"])
        amount = parse_major_amount(data["amount"], currency)
    except KeyError as exc:
        raise AdapterError(f"deposit event is missing field {exc}") from exc
    if not amount.is_positive:
        raise AdapterError("deposit amount must be greater than zero")
    return DepositEvent(str(payload.get("id", "")), account_id, amount)


def apply_deposit(snapshot: TreasurySnapshot, event: DepositEvent) -> TreasurySnapshot:
    """New snapshot with the deposit credited. Input snapshot is untouched."""
    rows = list(snapshot.balances)
    for i, row in enumerate(rows):
        if row.account_id == event.account_id:
            if row.amount.currency != event.amount.currency:
                raise AdapterError(
                    f"account {event.account_id} currency {row.amount.currency} does not match deposit {event.amount.currency}"
                )
            rows[i] = Balance(row.account_id, row.amount + event.amount)
            return replace(snapshot, balances=tuple(rows))
    for i, row in enumerate(sorted(rows, key=lambda b: b.account_id)):
        if row.amount.currency == event.amount.currency:
            idx = rows.index(row)
            rows[idx] = Balance(row.account_id, row.amount + event.amount)
            return replace(snapshot, balances=tuple(rows))
    rows.append(Balance(event.account_id, event.amount))
    return replace(snapshot, balances=tuple(rows))


def handle_webhook(
    raw_body: bytes,
    signature: str | None,
    secret: str,
    snapshot: TreasurySnapshot,
    tokens: tuple[ApprovalToken, ...],
    seen_event_ids: set[str] | None = None,
) -> tuple[TreasurySnapshot, tuple[InvalidationResult, ...]]:
    if not verify_signature(raw_body, signature, secret):
        raise SignatureError("webhook signature verification failed")
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdapterError("webhook body is not valid JSON") from exc
    event = parse_deposit_event(payload)
    if seen_event_ids is not None and event.event_id:
        if event.event_id in seen_event_ids:
            raise DuplicateWebhookError(f"webhook event {event.event_id!r} was already processed")
        seen_event_ids.add(event.event_id)
    updated = apply_deposit(snapshot, event)
    return updated, invalidate_changed(tokens, updated)
