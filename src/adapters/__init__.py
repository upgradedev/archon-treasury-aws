"""Adapters live outside the pure kerdon core and implement its ports."""

from adapters.airwallex_client import (
    AdapterError,
    AirwallexClient,
    DuplicateRequestError,
    FakeAirwallexTransport,
    build_deposit_simulation_payload,
    build_fx_quote_payload,
    build_transfer_payload,
    parse_major_amount,
    to_airwallex_amount,
)
from adapters.webhook import (
    DepositEvent,
    SignatureError,
    apply_deposit,
    handle_webhook,
    parse_deposit_event,
    sign_payload,
    verify_signature,
)

__all__ = [
    "AdapterError",
    "AirwallexClient",
    "DepositEvent",
    "DuplicateRequestError",
    "FakeAirwallexTransport",
    "SignatureError",
    "apply_deposit",
    "build_deposit_simulation_payload",
    "build_fx_quote_payload",
    "build_transfer_payload",
    "handle_webhook",
    "parse_deposit_event",
    "parse_major_amount",
    "sign_payload",
    "to_airwallex_amount",
    "verify_signature",
]
