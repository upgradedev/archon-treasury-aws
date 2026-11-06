"""Lambda Function URL adapter for the same demo the local server runs.

Event shape: payload format version 2. Each visitor gets an opaque
session cookie and an isolated DemoService (archon_demo.sessions), so one
judge cannot move another judge's money. State lives per warm container
and a cold start reseeds the synthetic scenario; the page says so.
Packaging: zip src/ with this module as the handler entry
(archon_demo.lambda_handler.handler), Python 3.12 runtime, no layers.
"""

import base64
import json
import os

from archon_demo.page import PAGE
from archon_demo.sessions import SessionStore, cookie_value, parse_cookie
from kerdon.errors import DomainError

STORE = SessionStore()
MAX_BODY_BYTES = 16384

SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def _response(status, body, content_type="application/json", set_cookie=None):
    out = {
        "statusCode": status,
        "headers": {"Content-Type": content_type, **SECURITY_HEADERS},
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
) -> tuple[int, str | dict, str, str | None]:
    """Single Front Controller shared by Lambda Function URL and local HTTP server."""
    read_method = method in ("GET", "HEAD")
    session_id, service, is_new = store.resolve(parse_cookie(raw_cookie))
    set_cookie = cookie_value(session_id) if is_new else None
    try:
        if len(raw.encode("utf-8")) > MAX_BODY_BYTES:
            return 413, {"error": "request body too large"}, "application/json", set_cookie
        if read_method and path == "/":
            return 200, ("" if method == "HEAD" else PAGE), "text/html; charset=utf-8", set_cookie
        if read_method and path == "/healthz":
            return 200, {"status": "ok"}, "application/json", None
        if read_method and path == "/DEPLOYED_SHA":
            return 200, {"deployed_sha": os.environ.get("DEPLOYED_SHA", default_sha)}, "application/json", None
        if read_method and path == "/favicon.ico":
            return 204, "", "image/x-icon", None
        if read_method and path == "/api/state":
            return 200, service.state(), "application/json", set_cookie
        if method == "POST" and path.startswith("/api/approve/"):
            return 200, service.approve(path.rsplit("/", 1)[1]), "application/json", set_cookie
        if method == "POST" and path.startswith("/api/execute/"):
            payload = _parse_json_object(raw)
            expected_sha = str(payload["approval_sha256"]) if payload.get("approval_sha256") else None
            return 200, service.execute(path.rsplit("/", 1)[1], expected_sha), "application/json", set_cookie
        if method == "POST" and path == "/api/simulate-deposit":
            payload = _parse_json_object(raw)
            if "currency" not in payload or "amount" not in payload:
                raise ValueError("currency and amount are required")
            return (
                200,
                service.simulate_deposit(str(payload["currency"]), str(payload["amount"])),
                "application/json",
                set_cookie,
            )
        if method == "POST" and path.startswith("/api/metal-call/"):
            return 200, service.pay_metal_call(path.rsplit("/", 1)[1]), "application/json", set_cookie
        if method == "POST" and path == "/api/metal-rebalance":
            payload = _parse_json_object(raw)
            if "agent_id" not in payload or "new_price" not in payload:
                raise ValueError("agent_id and new_price are required")
            return (
                200,
                service.rebalance_metal(str(payload["agent_id"]), str(payload["new_price"])),
                "application/json",
                set_cookie,
            )
        if method == "POST" and path == "/api/metal-mandate":
            payload = _parse_json_object(raw)
            if "agent_id" not in payload or "new_max_price_cents" not in payload:
                raise ValueError("agent_id and new_max_price_cents are required")
            return (
                200,
                service.replace_metal_mandate(str(payload["agent_id"]), int(payload["new_max_price_cents"])),
                "application/json",
                set_cookie,
            )
        if method == "POST" and path == "/api/metal-dispute":
            return 200, service.resolve_metal_dispute(), "application/json", set_cookie
        if method == "POST" and path == "/api/customer-email":
            payload = _parse_json_object(raw)
            contradicts = bool(payload.get("contradicts", True))
            return 200, service.apply_customer_email(contradicts), "application/json", set_cookie
        if method == "POST" and path == "/api/evaluate-invoice":
            payload = _parse_json_object(raw)
            oid = str(payload.get("obligation_id", "obl-usd-1"))
            mode = str(payload.get("mode", "matching"))
            return 200, service.inspect_invoice(oid, mode), "application/json", set_cookie
        if method == "POST" and path == "/api/incident-fail":
            payload = _parse_json_object(raw)
            ftype = str(payload.get("failure_type", "bank_return"))
            return 200, service.trigger_incident_failure(ftype), "application/json", set_cookie
        if method == "POST" and path == "/api/incident-resolve":
            return 200, service.resolve_incident(), "application/json", set_cookie
        if method == "POST" and path == "/api/reset":
            service.reset()
            return 200, {"state": "reset"}, "application/json", set_cookie
        return 404, {"error": "not found"}, "application/json", None
    except DomainError as exc:
        return 409, {"error": str(exc)}, "application/json", set_cookie
    except (KeyError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return 400, {"error": f"bad request: {exc}"}, "application/json", set_cookie


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
    status, body, content_type, set_cookie = dispatch_http(STORE, method, path, raw, raw_cookie)
    return _response(status, body, content_type, set_cookie)
