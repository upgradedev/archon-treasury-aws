"""Operational helpers for DemoService: FX pair ratios, reconciliation, integration status, and state serialization."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import json
import os

from adapters.airwallex_client import parse_major_amount
from adapters.fx_rates_client import get_fx_rates
from adapters.live_transport import (
    HttpAirwallexTransport,
    live_credentials_present,
    resolve_airwallex_mode_label,
)
from adapters.metal_client import AgentBudget, MetalSpendGovernor
from adapters.webhook import handle_webhook, sign_payload
from archon_demo.persistence import deserialize_snapshot, deserialize_token, serialize_snapshot, serialize_token
from kerdon.approvals import ApprovalState, RequestIdLedger, invalidate_changed
from kerdon.completeness import evaluate
from kerdon.errors import DomainError
from kerdon.models import Balance, FxQuote, ObligationStatus
from kerdon.money import Money
from kerdon.planner import TransferLifecycle
from kerdon.ports import ExecutionGate


def fx_pair_ratio(sell_currency: str, buy_currency: str) -> tuple[int, int]:
    rates = get_fx_rates()
    pair = (sell_currency.upper(), buy_currency.upper())
    if pair == ("EUR", "USD"):
        return int(rates["eur_usd_bps"]), 10_000
    if pair == ("USD", "EUR"):
        return 10_000, int(rates["eur_usd_bps"])
    if pair == ("EUR", "GBP"):
        return int(rates["eur_gbp_bps"]), 10_000
    if pair == ("GBP", "EUR"):
        return 10_000, int(rates["eur_gbp_bps"])
    if pair == ("GBP", "USD"):
        return int(rates["gbp_usd_bps"]), 10_000
    if pair == ("USD", "GBP"):
        return 10_000, int(rates["gbp_usd_bps"])
    raise DomainError(f"unsupported FX currency pair {sell_currency}/{buy_currency}")


def compute_reconciliation(svc: object) -> dict:
    approved_shas = {p.approval_sha256 for p in svc.snapshot.pending_approvals}
    unmatched_executions = [
        x.execution_id for x in svc.snapshot.executions if x.approval_sha256 not in approved_shas
    ]
    paid_obligations = [
        o.obligation_id for o in svc.snapshot.obligations if o.status is ObligationStatus.PAID
    ]
    missing_transfers = [oid for oid in paid_obligations if oid not in svc.transfers]
    findings = evaluate(svc.snapshot)
    r01_r02 = [f.rule_id for f in findings if f.rule_id in ("R01", "R02", "R14", "R21")]
    return {
        "tenant_id": svc.tenant_id,
        "reconciled_at": svc.snapshot.as_of.isoformat(),
        "executions_count": len(svc.snapshot.executions),
        "transfers_recorded": len(svc.transfers),
        "deposits_recorded": len(svc.deposit_history),
        "fx_conversions_recorded": len(svc.fx_conversions),
        "unmatched_executions": unmatched_executions,
        "missing_transfer_ids": missing_transfers,
        "ledger_findings": r01_r02,
        "execution_integrity_ok": len(unmatched_executions) == 0 and len(missing_transfers) == 0,
    }


def compute_integration_status(svc: object, bedrock_calls: int, bedrock_max_calls: int) -> dict:
    is_http_awx = isinstance(svc.transport, HttpAirwallexTransport)
    awx_mode = resolve_airwallex_mode_label(svc.transport) if is_http_awx else "synthetic-demo-fake-transport"
    bedrock_live = os.environ.get("ARCHON_ENABLE_LIVE_BEDROCK") == "1"
    fx_info = get_fx_rates()
    return {
        "airwallex": {
            "provider": "Airwallex Core API & Webhooks",
            "mode": awx_mode,
            "live_transport_active": is_http_awx,
            "credentials_configured": live_credentials_present(),
            "decoupled_from_bedrock": True,
            "webhook_replay_protection": True,
            "seen_webhook_events": len(svc.seen_webhook_ids),
        },
        "bedrock": {
            "provider": "Amazon Bedrock (Claude Haiku 4.5 Evaluator)",
            "mode": "amazon-bedrock-live" if bedrock_live else "deterministic-evaluator-port",
            "live_enabled": bedrock_live,
            "calls_used": bedrock_calls,
            "calls_cap": bedrock_max_calls,
            "write_capability": "DENIED (Evaluator Port)",
        },
        "fx_feed": {
            "provider": "European Central Bank Reference Feed",
            "source": fx_info.get("source", "ecb-reference-rates-pinned-offline"),
            "as_of_date": fx_info.get("as_of_date", "2026-11-05"),
        },
        "metal_x402": {
            "provider": "Metal L1 Testnet (*USDZ) x402 Governor",
            "mode": "simulated-metal-x402-adapter",
            "live_transport_active": False,
            "note": "Deterministic local x402 signature & spend-cap adapter (not live mainnet).",
        },
        "visa_virtual_cards": {
            "provider": "Visa Commercial Single-Use Virtual Card Mandate",
            "mode": "deterministic-mcc-mandate-engine",
            "live_transport_active": False,
            "allowed_mcc": svc.visa_mandate.allowed_mcc,
        },
    }


def serialize_service_state(svc: object) -> dict:
    return {
        "tenant_id": svc.tenant_id,
        "is_live_tenant": svc.is_live_tenant,
        "snapshot": serialize_snapshot(svc.snapshot),
        "tokens": {oid: serialize_token(tok) for oid, tok in svc.tokens.items()},
        "approvers_by_obligation": dict(svc.approvers_by_obligation),
        "receipts": dict(svc.receipts),
        "transfers": dict(svc.transfers),
        "deposit_history": list(svc.deposit_history),
        "fx_conversions": list(svc.fx_conversions),
        "seen_webhook_ids": sorted(svc.seen_webhook_ids),
        "contradicted_by_email": svc.contradicted_by_email,
        "deposit_confirmed": svc.deposit_confirmed,
        "last_dispute_report": svc.last_dispute_report,
        "last_ai_inspection": svc.last_ai_inspection,
        "incident": {
            "status": svc.incident.status.value,
            "failure_type": svc.incident.failure_type,
            "replacement_transfer_id": svc.incident.replacement_transfer_id,
            "replacement_request_id": svc.incident.replacement_request_id,
        },
        "visa_mandate": {
            "status": svc.visa_mandate.status.value,
            "card_last4": svc.visa_mandate.card_last4,
            "last_verdict": svc.visa_mandate.last_verdict,
            "last_reason": svc.visa_mandate.last_reason,
            "rebate_earned_cents": svc.visa_mandate.rebate_earned_cents,
        },
        "metal_state": {
            "calls": dict(svc.metal._calls),
            "budgets": [
                {
                    "agent_id": b.agent_id,
                    "weight": b.weight,
                    "price_cents": b.price_per_call.amount_cents,
                    "max_price_per_call_cents": b.max_price_per_call_cents,
                }
                for b in svc.metal.budgets
            ],
        },
        "request_ledger": {
            req_id: {"op_sha256": op_sha, "first_seen": first_seen.isoformat()}
            for req_id, (op_sha, first_seen) in svc._gate.ledger._seen.items()
        },
    }


def deserialize_service_state(cls: type, data: dict) -> object:
    snap = deserialize_snapshot(data["snapshot"])
    svc = cls(
        snapshot=snap,
        tenant_id=str(data.get("tenant_id", "demo-tenant")),
        is_live_tenant=bool(data.get("is_live_tenant", False)),
    )
    svc.tokens = {oid: deserialize_token(raw) for oid, raw in (data.get("tokens") or {}).items()}
    svc.approvers_by_obligation = dict(data.get("approvers_by_obligation") or {})
    svc.receipts = dict(data.get("receipts") or {})
    svc.transfers = dict(data.get("transfers") or {})
    svc.deposit_history = list(data.get("deposit_history") or [])
    svc.fx_conversions = list(data.get("fx_conversions") or [])
    svc.seen_webhook_ids = set(data.get("seen_webhook_ids") or [])
    svc.contradicted_by_email = bool(data.get("contradicted_by_email", False))
    svc.deposit_confirmed = bool(data.get("deposit_confirmed", False))
    svc.last_dispute_report = data.get("last_dispute_report")
    svc.last_ai_inspection = data.get("last_ai_inspection")
    inc_data = data.get("incident") or {}
    if inc_data:
        svc.incident = replace(
            svc.incident,
            status=TransferLifecycle(inc_data.get("status", svc.incident.status.value)),
            failure_type=inc_data.get("failure_type"),
            replacement_transfer_id=inc_data.get("replacement_transfer_id"),
            replacement_request_id=inc_data.get("replacement_request_id"),
        )
    vm_data = data.get("visa_mandate") or {}
    if vm_data:
        status_cls = type(svc.visa_mandate.status)
        svc.visa_mandate = replace(
            svc.visa_mandate,
            status=status_cls(vm_data.get("status", svc.visa_mandate.status.value)),
            card_last4=vm_data.get("card_last4"),
            last_verdict=vm_data.get("last_verdict"),
            last_reason=vm_data.get("last_reason"),
            rebate_earned_cents=int(vm_data.get("rebate_earned_cents", 0)),
        )
    m_data = data.get("metal_state") or {}
    if m_data:
        if m_data.get("budgets"):
            svc.metal = MetalSpendGovernor(
                total_budget=svc.metal.total_budget,
                budgets=tuple(
                    AgentBudget(
                        b["agent_id"],
                        int(b["weight"]),
                        Money(int(b["price_cents"]), "USDZ"),
                        max_price_per_call_cents=int(b["max_price_per_call_cents"]),
                    )
                    for b in m_data["budgets"]
                ),
                transport=svc.metal.transport,
            )
        for aid, cnt in (m_data.get("calls") or {}).items():
            svc.metal._calls[str(aid)] = int(cnt)
    seen_ledger = {}
    for req_id, entry in (data.get("request_ledger") or {}).items():
        seen_ledger[req_id] = (str(entry["op_sha256"]), datetime.fromisoformat(entry["first_seen"]))
    svc._gate = ExecutionGate(RequestIdLedger(_seen=seen_ledger))
    return svc


def run_signed_webhook(
    svc: object,
    raw_body: bytes,
    signature: str | None,
    secret: str,
    account_by_currency: dict[str, str],
) -> dict:
    tokens = tuple(svc.tokens.values())
    svc.snapshot, results = handle_webhook(
        raw_body, signature, secret, svc.snapshot, tokens, seen_event_ids=svc.seen_webhook_ids
    )
    payload = json.loads(raw_body.decode("utf-8"))
    data = payload.get("data", payload)
    currency = str(data["currency"])
    money = parse_major_amount(data["amount"], currency)
    evt_id = str(payload.get("id", f"evt-wh-{len(svc.deposit_history) + 1}"))
    invalidated = sorted(
        r.token.intent.obligation_id for r in results if r.state is ApprovalState.INVALIDATED
    )
    still_valid = sorted(
        r.token.intent.obligation_id for r in results if r.state is ApprovalState.VALID
    )
    svc.deposit_confirmed = True
    svc.contradicted_by_email = False
    svc.deposit_history.append(
        {
            "deposit_id": f"dep-{len(svc.deposit_history) + 1}",
            "event_id": evt_id,
            "account_id": str(data.get("global_account_id", account_by_currency.get(currency, ""))),
            "currency": currency,
            "amount": money.spoken(),
            "amount_major": f"{currency} {money.to_major_str()}",
            "amount_cents": money.amount_cents,
            "payer_name": str(data.get("payer_name", "Signed Webhook Event")),
            "reference": str(data.get("reference", f"WH-{evt_id}")),
            "recorded_at": svc.snapshot.as_of.isoformat(),
            "invalidated": invalidated,
            "still_valid": still_valid,
        }
    )
    return {
        "event_id": evt_id,
        "currency": currency,
        "amount": money.spoken(),
        "invalidated": invalidated,
        "still_valid": still_valid,
    }


def run_update_reserve_floor(
    svc: object, currency: str, reserve_floor_major: str, account_by_currency: dict[str, str]
) -> dict:
    cur = str(currency).upper()
    if cur not in account_by_currency:
        raise DomainError(f"unsupported currency {currency!r}")
    floor_money = parse_major_amount(reserve_floor_major, cur)
    if floor_money.amount_cents < 0:
        raise DomainError("reserve floor cannot be negative")
    kept = tuple(f for f in svc.snapshot.reserve_floors if f.currency != cur)
    svc.snapshot = replace(svc.snapshot, reserve_floors=kept + (floor_money,))
    results = invalidate_changed(tuple(svc.tokens.values()), svc.snapshot)
    return {
        "currency": cur,
        "reserve_floor": floor_money.spoken(),
        "reserve_floor_major": f"{cur} {floor_money.to_major_str()}",
        "reserve_floor_cents": floor_money.amount_cents,
        "invalidated": sorted(
            r.token.intent.obligation_id for r in results if r.state is ApprovalState.INVALIDATED
        ),
        "still_valid": sorted(
            r.token.intent.obligation_id for r in results if r.state is ApprovalState.VALID
        ),
    }


def run_create_fx_quote(
    svc: object, sell_currency: str, buy_currency: str, sell_amount_major: str, ttl_seconds: int = 300
) -> dict:
    sell_cur = str(sell_currency).upper()
    buy_cur = str(buy_currency).upper()
    if sell_cur == buy_cur:
        raise DomainError("sell_currency and buy_currency must differ")
    source_money = parse_major_amount(sell_amount_major, sell_cur)
    if not source_money.is_positive:
        raise DomainError("FX quote sell amount must be greater than zero")
    num, den = fx_pair_ratio(sell_cur, buy_cur)
    target_cents = (source_money.amount_cents * num) // den
    target_money = Money(target_cents, buy_cur)
    quote_id = f"fxq-{len(svc.snapshot.fx_quotes) + len(svc.fx_conversions) + 1}"
    expires_at = svc.snapshot.as_of + timedelta(seconds=int(ttl_seconds))
    quote = FxQuote(
        quote_id=quote_id,
        from_currency=sell_cur,
        to_currency=buy_cur,
        source_amount=source_money,
        rate_numerator=num,
        rate_denominator=den,
        expires_at=expires_at,
    )
    svc.snapshot = replace(svc.snapshot, fx_quotes=svc.snapshot.fx_quotes + (quote,))
    return {
        "quote_id": quote_id,
        "from_currency": sell_cur,
        "to_currency": buy_cur,
        "sell_amount": source_money.spoken(),
        "sell_amount_major": f"{sell_cur} {source_money.to_major_str()}",
        "buy_amount": target_money.spoken(),
        "buy_amount_major": f"{buy_cur} {target_money.to_major_str()}",
        "rate_numerator": num,
        "rate_denominator": den,
        "expires_at": expires_at.isoformat(),
        "expired": expires_at <= svc.snapshot.as_of,
    }


def run_execute_fx_conversion(
    svc: object, quote_id: str, account_by_currency: dict[str, str]
) -> dict:
    quote = svc.snapshot.fx_quote(quote_id)
    if quote is None:
        raise DomainError(f"unknown FX quote {quote_id!r}")
    if quote.expires_at <= svc.snapshot.as_of:
        raise DomainError(f"FX quote {quote_id} has expired and cannot be executed")
    sell_cur = quote.from_currency
    buy_cur = quote.to_currency
    sell_balance = svc.snapshot.balance_cents(sell_cur)
    sell_floor = svc.snapshot.reserve_floor_cents(sell_cur)
    if sell_balance - quote.source_amount.amount_cents < sell_floor:
        raise DomainError(f"FX conversion would breach the {sell_cur} reserve floor")
    buy_cents = (quote.source_amount.amount_cents * quote.rate_numerator) // quote.rate_denominator
    buy_money = Money(buy_cents, buy_cur)
    new_balances = []
    for b in svc.snapshot.balances:
        if b.amount.currency == sell_cur and b.account_id == account_by_currency.get(sell_cur):
            new_balances.append(
                Balance(b.account_id, Money(b.amount.amount_cents - quote.source_amount.amount_cents, sell_cur))
            )
        elif b.amount.currency == buy_cur and b.account_id == account_by_currency.get(buy_cur):
            new_balances.append(
                Balance(b.account_id, Money(b.amount.amount_cents + buy_cents, buy_cur))
            )
        else:
            new_balances.append(b)
    remaining_quotes = tuple(q for q in svc.snapshot.fx_quotes if q.quote_id != quote_id)
    svc.snapshot = replace(svc.snapshot, balances=tuple(new_balances), fx_quotes=remaining_quotes)
    results = invalidate_changed(tuple(svc.tokens.values()), svc.snapshot)
    conv = {
        "conversion_id": f"fxc-{len(svc.fx_conversions) + 1}",
        "quote_id": quote_id,
        "from_currency": sell_cur,
        "to_currency": buy_cur,
        "sold_major": f"{sell_cur} {quote.source_amount.to_major_str()}",
        "bought_major": f"{buy_cur} {buy_money.to_major_str()}",
        "rate_numerator": quote.rate_numerator,
        "rate_denominator": quote.rate_denominator,
        "executed_at": svc.snapshot.as_of.isoformat(),
        "invalidated": sorted(
            r.token.intent.obligation_id for r in results if r.state is ApprovalState.INVALIDATED
        ),
    }
    svc.fx_conversions.append(conv)
    return conv


def run_deposit_locked(
    svc: object,
    currency: str,
    amount_major: str,
    payer_name: str,
    reference: str | None,
    event_id: str | None,
    account_by_currency: dict[str, str],
    webhook_secret: str,
) -> dict:
    money = parse_major_amount(amount_major, currency)
    if not money.is_positive:
        raise DomainError("deposit amount must be greater than zero")
    account = account_by_currency.get(currency)
    if account is None:
        raise DomainError(f"no demo account for currency {currency!r}")
    evt_id = event_id or f"evt-demo-{len(svc.deposit_history) + len(getattr(svc.transport, 'calls', ())) + 1}"
    body = json.dumps(
        {
            "id": evt_id,
            "data": {"global_account_id": account, "currency": currency, "amount": money.to_major_str()},
        }
    ).encode()
    tokens = tuple(svc.tokens.values())
    svc.snapshot, results = handle_webhook(
        body,
        sign_payload(body, webhook_secret),
        webhook_secret,
        svc.snapshot,
        tokens,
        seen_event_ids=svc.seen_webhook_ids,
    )
    svc.deposit_confirmed = True
    svc.contradicted_by_email = False
    invalidated = sorted(
        r.token.intent.obligation_id for r in results if r.state is ApprovalState.INVALIDATED
    )
    still_valid = sorted(
        r.token.intent.obligation_id for r in results if r.state is ApprovalState.VALID
    )
    record = {
        "deposit_id": f"dep-{len(svc.deposit_history) + 1}",
        "event_id": evt_id,
        "account_id": account,
        "currency": currency,
        "amount": money.spoken(),
        "amount_major": f"{currency} {money.to_major_str()}",
        "amount_cents": money.amount_cents,
        "payer_name": payer_name,
        "reference": reference or f"REF-{evt_id.upper()}",
        "recorded_at": svc.snapshot.as_of.isoformat(),
        "invalidated": invalidated,
        "still_valid": still_valid,
    }
    svc.deposit_history.append(record)
    return {
        "deposit_id": record["deposit_id"],
        "event_id": evt_id,
        "currency": currency,
        "amount": money.spoken(),
        "amount_major": record["amount_major"],
        "payer_name": payer_name,
        "reference": record["reference"],
        "invalidated": invalidated,
        "still_valid": still_valid,
    }


def build_audit_csv(state: dict) -> str:
    lines = [
        "obligation_id,supplier_name,invoice_ref,currency,amount_major,rail,rail_fee,plan_action,approval_state,approval_sha256,merkle_root_sha256"
    ]
    for o in state["obligations"]:
        rec = o.get("receipt") or {}
        lines.append(
            ",".join(
                [
                    str(o["obligation_id"]),
                    f'"{o["supplier_name"]}"',
                    str(o["invoice_ref"]),
                    str(o["currency"]),
                    str(o["amount_major"]),
                    str(o["rail"]),
                    f'"{o["rail_fee"]}"',
                    str(o["plan_action"]),
                    str(o["approval_state"]),
                    str(o.get("approval_sha256") or ""),
                    str(rec.get("merkle_root_sha256") or ""),
                ]
            )
        )
    return "\n".join(lines) + "\n"


def incident_to_dict(inc: object) -> dict:
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


def visa_to_dict(vm: object) -> dict:
    return {
        "card_id": vm.card_id,
        "obligation_id": vm.obligation_id,
        "supplier_name": vm.supplier_name,
        "limit": vm.limit.spoken(),
        "limit_cents": vm.limit.amount_cents,
        "allowed_mcc": vm.allowed_mcc,
        "single_use": vm.single_use,
        "status": vm.status.value,
        "card_last4": vm.card_last4,
        "last_verdict": vm.last_verdict,
        "last_reason": vm.last_reason,
        "rebate_earned": Money(vm.rebate_earned_cents, vm.limit.currency).spoken(),
        "rebate_earned_cents": vm.rebate_earned_cents,
    }
