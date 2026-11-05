"""Airwallex boundary. The ONLY file allowed to convert cents to major units.

STATE.md section 6 rule 2: integer cents become decimal strings only here
(Trap T2: the REST API takes major units, so 5000 cents must leave this
process as the string "50.00", never as 5000). Inbound major-unit strings
become Money here too, parsed with integer math.

Transport is injected. This module opens no socket and reads no credential,
so every behavior below is testable offline. The live payload field layout
is marked ESTIMATE until the owner completes O-2 sandbox signup and one
real sandbox call confirms it; the conversion and idempotency contracts do
not depend on that layout.
"""

import json
from dataclasses import dataclass, field
from typing import Callable

from kerdon.approvals import ApprovalIntent
from kerdon.errors import DomainError
from kerdon.money import Money
from kerdon.models import Balance

Transport = Callable[[str, str, dict | None], dict]


class AdapterError(DomainError):
    """Transport or payload failure at the Airwallex boundary."""


class DuplicateRequestError(AdapterError):
    """Mirror of the API duplicate_request_id refusal (Trap T3)."""


def to_airwallex_amount(money: Money) -> str:
    """5000 USD cents -> "50.00". The single outbound conversion point."""
    return money.to_major_str()


def parse_major_amount(value: object, currency: str) -> Money:
    """Parse a major-unit decimal string into integer cents. Fail closed.

    Accepts "50", "50.0", "50.00", "-1.23". Rejects non-strings, more than
    two decimal places, and anything that is not plain digits.
    """
    if not isinstance(value, str) or not value.strip():
        raise AdapterError(f"amount must be a decimal string, got {type(value).__name__}")
    text = value.strip()
    negative = text.startswith("-")
    text = text[1:] if negative or text.startswith("+") else text
    whole, dot, frac = text.partition(".")
    if not whole.isdigit() or len(whole) > 9 or (dot and not frac.isdigit()) or len(frac) > 2:
        raise AdapterError(f"amount {value!r} is not a 2-decimal major-unit string")
    cents = int(whole) * 100 + int((frac + "00")[:2] or 0)
    return Money(-cents if negative else cents, currency)


def build_transfer_payload(intent: ApprovalIntent, request_id: str, beneficiary_id: str) -> dict:
    return {
        "request_id": request_id,
        "amount": to_airwallex_amount(Money(intent.amount_cents, intent.currency)),
        "currency": intent.currency,
        "beneficiary_id": beneficiary_id,
        "metadata": {
            "obligation_id": intent.obligation_id,
            "fx_quote_id": intent.fx_quote_id,
            "evidence_sha256": intent.evidence_sha256,
        },
    }


def build_fx_quote_payload(source: Money, to_currency: str, request_id: str) -> dict:
    return {
        "request_id": request_id,
        "from_currency": source.currency,
        "to_currency": to_currency,
        "from_amount": to_airwallex_amount(source),
    }


def build_deposit_simulation_payload(global_account_id: str, money: Money, payer_name: str | None = None) -> dict:
    """Trap T4: simulation deposits take NO currency field.

    The credited currency is the currency of the chosen global account.
    Sending currency here would be silently discarded by the API, so this
    builder refuses to include it.
    """
    if not money.is_positive:
        raise AdapterError("deposit amount must be greater than zero")
    payload = {"global_account_id": global_account_id, "amount": to_airwallex_amount(money)}
    if payer_name:
        payload["payer_name"] = payer_name
    return payload


@dataclass(slots=True)
class AirwallexClient:
    """Implements the kerdon WriterPort over an injected transport."""

    transport: Transport

    def execute(self, intent: ApprovalIntent, request_id: str) -> str:
        payload = build_transfer_payload(intent, request_id, intent.counterparty_id)
        response = self.transport("POST", "/api/v1/transfers/create", payload)
        transfer_id = response.get("id")
        if not isinstance(transfer_id, str) or not transfer_id:
            raise AdapterError("transfer response carries no id")
        return transfer_id

    def create_fx_quote(self, source: Money, to_currency: str, request_id: str) -> dict:
        return self.transport(
            "POST", "/api/v1/fx/quotes/create", build_fx_quote_payload(source, to_currency, request_id)
        )

    def simulate_deposit(self, global_account_id: str, money: Money, payer_name: str | None = None) -> dict:
        return self.transport(
            "POST",
            "/api/v1/simulation/deposit/create",
            build_deposit_simulation_payload(global_account_id, money, payer_name),
        )

    def get_balances(self) -> tuple[Balance, ...]:
        response = self.transport("GET", "/api/v1/balances", None)
        rows = response.get("items", [])
        out = []
        for row in rows:
            out.append(
                Balance(
                    str(row["account_id"]),
                    parse_major_amount(row["amount"], str(row["currency"])),
                )
            )
        return tuple(sorted(out, key=lambda b: b.account_id))


@dataclass(slots=True)
class FakeAirwallexTransport:
    """In-memory sandbox double with real idempotency semantics (Trap T3).

    Same request_id plus same payload returns the first response again.
    Same request_id plus a different payload raises DuplicateRequestError,
    mirroring the API duplicate_request_id refusal.
    """

    balance_rows: list[dict] = field(default_factory=list)
    calls: list[tuple[str, str, dict | None]] = field(default_factory=list)
    _transfers: dict[str, tuple[str, dict]] = field(default_factory=dict)
    _counter: int = 0

    def __call__(self, method: str, path: str, payload: dict | None) -> dict:
        self.calls.append((method, path, payload))
        if method == "GET" and path == "/api/v1/balances":
            return {"items": list(self.balance_rows)}
        if method == "POST" and path == "/api/v1/transfers/create":
            assert payload is not None
            request_id = str(payload["request_id"])
            fingerprint = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            prior = self._transfers.get(request_id)
            if prior is not None:
                if prior[0] != fingerprint:
                    raise DuplicateRequestError("duplicate_request_id")
                return dict(prior[1])
            self._counter += 1
            response = {"id": f"trn_fake_{self._counter}", "status": "SENT", "request_id": request_id}
            self._transfers[request_id] = (fingerprint, response)
            return dict(response)
        if method == "POST" and path == "/api/v1/fx/quotes/create":
            assert payload is not None
            return {"id": "fx_fake_1", "status": "LOCKED", **payload}
        if method == "POST" and path == "/api/v1/simulation/deposit/create":
            assert payload is not None
            return {"id": "dep_fake_1", "status": "ACCEPTED", **payload}
        raise AdapterError(f"fake transport has no route for {method} {path}")

    @property
    def transfer_count(self) -> int:
        return len(self._transfers)
