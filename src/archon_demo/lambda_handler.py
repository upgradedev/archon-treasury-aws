"""Lambda Function URL and HTTP Front Controller for Archon Treasury.

Supports:
- Legacy Python HTML at / (default) and /legacy, plus static React SPA at /app
  (and at / when ARCHON_SERVE_REACT_UI=1) with /assets/* static asset serving.
- Per-visitor and per-tenant sessions backed by SQLite WAL durability (archon_demo.sessions).
- Least-privilege RBAC (READER, EVALUATOR, APPROVER, WRITER, ADMIN), Separation of Duties,
  and constant-time CSRF token enforcement.
- Persistent deposits, reserve-floor management, standalone FX quotes & conversions,
  signed webhooks with replay protection, provider status, ledger reconciliation,
  metrics/telemetry, and checksummed tenant backup/restore.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import time
from pathlib import Path

from adapters.airwallex_client import AdapterError
from adapters.webhook import DuplicateWebhookError, SignatureError
from archon_demo.auth import AuthorizationError, verify_csrf_token
from archon_demo.observability import TELEMETRY
from archon_demo.page import PAGE
from archon_demo.persistence import default_db_path
from archon_demo.sessions import SessionStore, cookie_value, parse_cookie
from kerdon.errors import DomainError

STORE = SessionStore(db_path=default_db_path())
MAX_BODY_BYTES = 16384

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    ),
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def _find_frontend_dist() -> Path | None:
    here = Path(__file__).resolve().parent
    bundled = here / "static"
    if (bundled / "index.html").is_file():
        return bundled
    repo_dist = here.parents[1] / "frontend" / "dist"
    if (repo_dist / "index.html").is_file():
        return repo_dist
    return None


def _serve_static_asset(rel_path: str) -> tuple[int, str, str] | None:
    dist = _find_frontend_dist()
    if dist is None:
        return None
    clean = rel_path.lstrip("/")
    if ".." in clean or "\\" in clean:
        return None
    target = (dist / clean).resolve()
    try:
        target.relative_to(dist.resolve())
    except ValueError:
        return None
    if not target.is_file():
        return None
    mime, _ = mimetypes.guess_type(str(target))
    ctype = mime or "application/octet-stream"
    if ctype.startswith("text/") or ctype in ("application/javascript", "application/json", "image/svg+xml"):
        return 200, target.read_text(encoding="utf-8"), f"{ctype}; charset=utf-8"
    return None


def _response(status, body, content_type="application/json", set_cookie=None, extra_headers=None):
    headers = {"Content-Type": content_type, **SECURITY_HEADERS}
    if extra_headers:
        headers.update(extra_headers)
    out = {
        "statusCode": status,
        "headers": headers,
        "body": body if isinstance(body, str) else json.dumps(body, indent=2),
    }
    if set_cookie:
        out["cookies"] = [set_cookie]
    return out


def _parse_json_object(raw: str) -> dict:
    payload = json.loads(raw or "{}")
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    return payload


def dispatch_http(
    store: SessionStore,
    method: str,
    path: str,
    raw: str,
    raw_cookie: str | None,
    default_sha: str = "not-set",
    headers: dict[str, str] | None = None,
) -> tuple[int, str | dict, str, str | None]:
    """Single Front Controller shared by Lambda Function URL and local HTTP server."""
    t0 = time.perf_counter()
    norm_headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    clean_path = path.split("?", 1)[0]
    read_method = method in ("GET", "HEAD")
    session_id, service, principal, is_new = store.resolve_with_principal(parse_cookie(raw_cookie))
    set_cookie = cookie_value(session_id) if is_new else None

    def _finish(status: int, body: str | dict, ctype: str, cookie: str | None = set_cookie):
        latency_ms = max(1, int((time.perf_counter() - t0) * 1000))
        TELEMETRY.record_request(method, clean_path, status, latency_ms, tenant_id=principal.tenant_id)
        return status, body, ctype, cookie

    try:
        if len(raw.encode("utf-8")) > MAX_BODY_BYTES:
            return _finish(413, {"error": "request body too large"}, "application/json")

        # Static asset serving (/assets/*)
        if read_method and clean_path.startswith("/assets/"):
            asset = _serve_static_asset(clean_path)
            if asset is not None:
                st, text_body, ctype = asset
                return _finish(st, ("" if method == "HEAD" else text_body), ctype, None)
            return _finish(404, {"error": "asset not found"}, "application/json", None)

        # Legacy Python UI explicitly at /legacy, or at / when ARCHON_SERVE_REACT_UI != 1
        if read_method and clean_path == "/legacy":
            return _finish(200, ("" if method == "HEAD" else PAGE), "text/html; charset=utf-8")

        if read_method and (clean_path == "/app" or clean_path.startswith("/app/")):
            spa = _serve_static_asset("index.html")
            if spa is not None:
                return _finish(200, ("" if method == "HEAD" else spa[1]), "text/html; charset=utf-8")
            return _finish(200, ("" if method == "HEAD" else PAGE), "text/html; charset=utf-8")

        if read_method and clean_path == "/":
            if os.environ.get("ARCHON_SERVE_REACT_UI") == "1":
                spa = _serve_static_asset("index.html")
                if spa is not None:
                    return _finish(200, ("" if method == "HEAD" else spa[1]), "text/html; charset=utf-8")
            return _finish(200, ("" if method == "HEAD" else PAGE), "text/html; charset=utf-8")

        if read_method and clean_path == "/healthz":
            return _finish(200, {"status": "ok"}, "application/json", None)
        if read_method and clean_path == "/DEPLOYED_SHA":
            return _finish(200, {"deployed_sha": os.environ.get("DEPLOYED_SHA", default_sha)}, "application/json", None)
        if read_method and clean_path == "/favicon.ico":
            return _finish(204, "", "image/x-icon", None)

        # Signed external webhook route (uses HMAC signature, not session CSRF)
        if method == "POST" and clean_path == "/api/webhooks/airwallex":
            sig = norm_headers.get("x-airwallex-signature") or norm_headers.get("x-signature")
            out = service.ingest_signed_webhook(raw.encode("utf-8"), sig)
            store.persist(session_id)
            store.persistence.record_audit_event(
                principal.tenant_id, "airwallex-webhook", "webhook.deposit", out
            )
            return _finish(200, out, "application/json")

        # Authentication routes
        if read_method and clean_path == "/api/auth/session":
            return _finish(200, principal.to_dict(), "application/json")

        if method == "POST" and clean_path == "/api/auth/signup":
            payload = _parse_json_object(raw)
            for req_field in ("email", "password", "tenant_id"):
                if req_field not in payload:
                    raise ValueError(f"{req_field} is required")
            new_p, new_svc = store.signup(
                session_id,
                email=str(payload["email"]),
                password=str(payload["password"]),
                display_name=str(payload.get("display_name", payload["email"])),
                tenant_id=str(payload["tenant_id"]),
                role=str(payload.get("role", "ADMIN")),
                separation_of_duties=bool(payload.get("separation_of_duties", False)),
                is_live_tenant=bool(payload.get("is_live_tenant", True)),
            )
            st = new_svc.state()
            st["session"] = new_p.to_dict()
            return _finish(200, {"session": new_p.to_dict(), "state": st}, "application/json", cookie_value(session_id))

        if method == "POST" and clean_path == "/api/auth/login":
            payload = _parse_json_object(raw)
            if "email" not in payload or "password" not in payload:
                raise ValueError("email and password are required")
            new_p, new_svc = store.login(
                session_id,
                email=str(payload["email"]),
                password=str(payload["password"]),
            )
            st = new_svc.state()
            st["session"] = new_p.to_dict()
            return _finish(200, {"session": new_p.to_dict(), "state": st}, "application/json", cookie_value(session_id))

        if method == "POST" and clean_path == "/api/auth/logout":
            anon_p = store.logout(session_id)
            return _finish(200, {"session": anon_p.to_dict()}, "application/json", cookie_value(session_id))

        # CSRF check for state-mutating POST requests when authenticated or when X-CSRF-Token is supplied
        if method == "POST":
            provided_csrf = norm_headers.get("x-csrf-token")
            require_csrf = (
                principal.authenticated
                or provided_csrf is not None
                or os.environ.get("ARCHON_REQUIRE_CSRF") == "1"
            )
            if require_csrf and not verify_csrf_token(principal.csrf_token, provided_csrf):
                TELEMETRY.record_security_event(
                    "csrf_rejected",
                    {"tenant_id": principal.tenant_id, "user_id": principal.user_id, "path": clean_path},
                )
                return _finish(403, {"error": "CSRF token missing or invalid"}, "application/json")

        if method == "POST" and clean_path == "/api/auth/role":
            payload = _parse_json_object(raw)
            if "role" not in payload:
                raise ValueError("role is required")
            updated_p = store.switch_role(
                session_id,
                role=str(payload["role"]),
                user_id=str(payload["user_id"]) if payload.get("user_id") else None,
                separation_of_duties=(
                    bool(payload["separation_of_duties"])
                    if "separation_of_duties" in payload
                    else None
                ),
            )
            return _finish(200, {"session": updated_p.to_dict()}, "application/json")

        if read_method and clean_path == "/api/state":
            principal.require_permission("read")
            st = service.state()
            st["session"] = principal.to_dict()
            return _finish(200, st, "application/json")

        if read_method and clean_path == "/api/audit-export.csv":
            principal.require_permission("export")
            return _finish(
                200,
                ("" if method == "HEAD" else service.export_audit_csv()),
                "text/csv; charset=utf-8",
            )

        if read_method and clean_path == "/api/integrations":
            principal.require_permission("read")
            return _finish(200, service.integration_status(), "application/json")

        if method == "POST" and clean_path == "/api/integrations/verify":
            principal.require_permission("read")
            return _finish(
                200,
                {
                    "verified": True,
                    "integrations": service.integration_status(probe_live=True),
                    "reconciliation": service.reconcile_ledger(),
                },
                "application/json",
            )

        if (read_method or method == "POST") and clean_path == "/api/reconcile":
            principal.require_permission("read" if read_method else "reconcile")
            return _finish(200, service.reconcile_ledger(), "application/json")

        if read_method and clean_path == "/api/metrics":
            principal.require_permission("read")
            metrics = TELEMETRY.snapshot()
            metrics["active_sessions"] = store.active_count()
            metrics["tenant_id"] = principal.tenant_id
            return _finish(200, metrics, "application/json")

        if read_method and clean_path == "/api/backup":
            principal.require_permission("backup")
            store.persist(session_id)
            return _finish(200, store.persistence.export_backup(principal.tenant_id), "application/json")

        if method == "POST" and clean_path == "/api/restore":
            principal.require_permission("backup")
            payload = _parse_json_object(raw)
            checksum = store.persistence.restore_backup(principal.tenant_id, payload)
            # Reload in-memory service from restored state
            restored_dict = store.persistence.load_tenant_state(principal.tenant_id)
            if restored_dict is not None:
                from archon_demo.service import DemoService
                restored_svc = DemoService.from_persisted_dict(restored_dict)
                store._services[principal.tenant_id] = (restored_svc, time.monotonic(), checksum)
            return _finish(200, {"restored": True, "sha256_checksum": checksum}, "application/json")

        if method == "POST" and clean_path.startswith("/api/approve/"):
            principal.require_permission("approve")
            oid = clean_path.rsplit("/", 1)[1]
            out = service.approve(oid, approver_id=principal.user_id)
            store.persist(session_id)
            store.persistence.record_audit_event(principal.tenant_id, principal.user_id, "payout.approve", out)
            return _finish(200, out, "application/json")

        if method == "POST" and clean_path.startswith("/api/execute/"):
            principal.require_permission("execute")
            oid = clean_path.rsplit("/", 1)[1]
            approver_id = service.approvers_by_obligation.get(oid)
            if approver_id:
                principal.check_separation_of_duties(approver_id)
            payload = _parse_json_object(raw)
            expected_sha = str(payload["approval_sha256"]) if payload.get("approval_sha256") else None
            out = service.execute(oid, expected_sha)
            store.persist(session_id)
            store.persistence.record_audit_event(principal.tenant_id, principal.user_id, "payout.execute", out)
            return _finish(200, out, "application/json")

        if method == "POST" and clean_path == "/api/simulate-deposit":
            principal.require_permission("deposit")
            payload = _parse_json_object(raw)
            if "currency" not in payload or "amount" not in payload:
                raise ValueError("currency and amount are required")
            out = service.simulate_deposit(str(payload["currency"]), str(payload["amount"]))
            store.persist(session_id)
            store.persistence.record_audit_event(principal.tenant_id, principal.user_id, "deposit.simulate", out)
            return _finish(200, out, "application/json")

        if method == "POST" and clean_path == "/api/deposits":
            principal.require_permission("deposit")
            payload = _parse_json_object(raw)
            if "currency" not in payload or "amount" not in payload:
                raise ValueError("currency and amount are required")
            out = service.record_deposit(
                currency=str(payload["currency"]),
                amount_major=str(payload["amount"]),
                payer_name=str(payload.get("payer_name", "Inbound Treasury Wire")),
                reference=str(payload["reference"]) if payload.get("reference") else None,
            )
            store.persist(session_id)
            store.persistence.record_audit_event(principal.tenant_id, principal.user_id, "deposit.record", out)
            return _finish(200, out, "application/json")

        if method == "POST" and clean_path == "/api/reserve-floor":
            principal.require_permission("floor")
            payload = _parse_json_object(raw)
            if "currency" not in payload or "reserve_floor" not in payload:
                raise ValueError("currency and reserve_floor are required")
            out = service.update_reserve_floor(str(payload["currency"]), str(payload["reserve_floor"]))
            store.persist(session_id)
            store.persistence.record_audit_event(principal.tenant_id, principal.user_id, "floor.update", out)
            return _finish(200, out, "application/json")

        if method == "POST" and clean_path == "/api/fx/quote":
            principal.require_permission("fx_quote")
            payload = _parse_json_object(raw)
            for req_field in ("sell_currency", "buy_currency", "sell_amount"):
                if req_field not in payload:
                    raise ValueError(f"{req_field} is required")
            ttl = int(payload.get("ttl_seconds", 300))
            out = service.create_fx_quote(
                str(payload["sell_currency"]),
                str(payload["buy_currency"]),
                str(payload["sell_amount"]),
                ttl_seconds=ttl,
            )
            store.persist(session_id)
            store.persistence.record_audit_event(principal.tenant_id, principal.user_id, "fx.quote", out)
            return _finish(200, out, "application/json")

        if method == "POST" and clean_path == "/api/fx/convert":
            principal.require_permission("fx_convert")
            payload = _parse_json_object(raw)
            if "quote_id" not in payload:
                raise ValueError("quote_id is required")
            out = service.execute_fx_conversion(str(payload["quote_id"]))
            store.persist(session_id)
            store.persistence.record_audit_event(principal.tenant_id, principal.user_id, "fx.convert", out)
            return _finish(200, out, "application/json")

        if method == "POST" and clean_path.startswith("/api/metal-call/"):
            principal.require_permission("metal")
            out = service.pay_metal_call(clean_path.rsplit("/", 1)[1])
            store.persist(session_id)
            return _finish(200, out, "application/json")

        if method == "POST" and clean_path == "/api/metal-rebalance":
            principal.require_permission("metal")
            payload = _parse_json_object(raw)
            if "agent_id" not in payload or "new_price" not in payload:
                raise ValueError("agent_id and new_price are required")
            out = service.rebalance_metal(str(payload["agent_id"]), str(payload["new_price"]))
            store.persist(session_id)
            return _finish(200, out, "application/json")

        if method == "POST" and clean_path == "/api/metal-mandate":
            principal.require_permission("metal")
            payload = _parse_json_object(raw)
            if "agent_id" not in payload or "new_max_price_cents" not in payload:
                raise ValueError("agent_id and new_max_price_cents are required")
            out = service.replace_metal_mandate(str(payload["agent_id"]), int(payload["new_max_price_cents"]))
            store.persist(session_id)
            return _finish(200, out, "application/json")

        if method == "POST" and clean_path == "/api/metal-dispute":
            principal.require_permission("metal")
            out = service.resolve_metal_dispute()
            store.persist(session_id)
            return _finish(200, out, "application/json")

        if method == "POST" and clean_path == "/api/customer-email":
            principal.require_permission("approve")
            payload = _parse_json_object(raw)
            contradicts = bool(payload.get("contradicts", True))
            out = service.apply_customer_email(contradicts)
            store.persist(session_id)
            return _finish(200, out, "application/json")

        if method == "POST" and clean_path == "/api/evaluate-invoice":
            principal.require_permission("evaluate")
            payload = _parse_json_object(raw)
            oid = str(payload.get("obligation_id", "obl-usd-1"))
            mode = str(payload.get("mode", "matching"))
            raw_custom = payload.get("custom_text") or payload.get("custom_invoice_text")
            custom_text = str(raw_custom) if raw_custom else None
            out = service.inspect_invoice(oid, mode, custom_text)
            store.persist(session_id)
            return _finish(200, out, "application/json")

        if method == "POST" and clean_path == "/api/visa-issue":
            principal.require_permission("visa")
            out = service.issue_visa_card()
            store.persist(session_id)
            return _finish(200, out, "application/json")

        if method == "POST" and clean_path == "/api/visa-charge":
            principal.require_permission("visa")
            payload = _parse_json_object(raw)
            charge_cents = int(payload.get("charge_cents", 450_00))
            mcc = str(payload.get("merchant_mcc", "5045"))
            out = service.charge_visa_card(charge_cents, mcc)
            store.persist(session_id)
            return _finish(200, out, "application/json")

        if method == "POST" and clean_path == "/api/incident-fail":
            principal.require_permission("incident")
            payload = _parse_json_object(raw)
            ftype = str(payload.get("failure_type", "bank_return"))
            out = service.trigger_incident_failure(ftype)
            store.persist(session_id)
            return _finish(200, out, "application/json")

        if method == "POST" and clean_path == "/api/incident-resolve":
            principal.require_permission("incident")
            out = service.resolve_incident()
            store.persist(session_id)
            return _finish(200, out, "application/json")

        if method == "POST" and clean_path == "/api/reset":
            service.reset()
            store.persist(session_id)
            return _finish(200, {"state": "reset"}, "application/json")

        return _finish(404, {"error": "not found"}, "application/json", None)
    except SignatureError as exc:
        TELEMETRY.record_security_event("webhook_signature_failed", {"error": str(exc)})
        return _finish(401, {"error": str(exc)}, "application/json")
    except DuplicateWebhookError as exc:
        TELEMETRY.record_security_event("webhook_replay_blocked", {"error": str(exc)})
        return _finish(409, {"error": str(exc)}, "application/json")
    except AuthorizationError as exc:
        TELEMETRY.record_security_event(
            "authorization_refused",
            {"tenant_id": principal.tenant_id, "user_id": principal.user_id, "role": principal.role.value, "error": str(exc)},
        )
        return _finish(403, {"error": str(exc)}, "application/json")
    except (DomainError, AdapterError) as exc:
        return _finish(409, {"error": str(exc)}, "application/json")
    except (KeyError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _finish(400, {"error": f"bad request: {exc}"}, "application/json")


def handler(event, _context=None):
    http = event.get("requestContext", {}).get("http", {})
    method, path = http.get("method", "GET"), http.get("path", "/")
    raw = event.get("body") or ""
    headers = {str(k).lower(): v for k, v in (event.get("headers") or {}).items()}
    raw_cookie = headers.get("cookie", "")
    if not raw_cookie and event.get("cookies"):
        raw_cookie = "; ".join(event["cookies"])
    if len(raw) > MAX_BODY_BYTES * 2:
        return _response(413, {"error": "request body too large"})
    if event.get("isBase64Encoded"):
        try:
            raw = base64.b64decode(raw).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            return _response(400, {"error": f"bad request: {exc}"})
    status, body, content_type, set_cookie = dispatch_http(
        STORE, method, path, raw, raw_cookie, headers=headers
    )
    extra = (
        {"Cache-Control": "public, max-age=31536000, immutable"}
        if path.startswith("/assets/") and status == 200
        else {"Cache-Control": "no-store"}
    )
    return _response(status, body, content_type, set_cookie, extra_headers=extra)
