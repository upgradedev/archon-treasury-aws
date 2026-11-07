"""Safe structured logging, secret/PII redaction, and operational metrics/tracing.

Enforces production gap #7:
- Never logs credentials, session cookies, tokens, or raw unstructured invoice text.
- Emits structured JSON log events with trace_id, tenant_id, actor, role, and latency_ms.
- Tracks operational counters, error rates, and latency telemetry for GET /api/metrics.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from collections import deque
from datetime import datetime, timezone

SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "awx_api_key",
        "client_id",
        "awx_client_id",
        "secret",
        "webhook_secret",
        "password",
        "password_hash",
        "token",
        "csrf_token",
        "authorization",
        "cookie",
        "set-cookie",
        "set_cookie",
        "signature",
        "custom_text",
        "invoice_text",
    }
)


def redact_value(key: str, value: object) -> object:
    """Redact credentials, cookies, tokens, and private invoice payloads."""
    low = key.lower().strip()
    if low in SENSITIVE_KEYS or any(s in low for s in ("secret", "password", "api_key", "token", "cookie")):
        return "[REDACTED]"
    return redact_payload(value)


def redact_payload(obj: object) -> object:
    """Recursively sanitize a payload before logging or audit persistence."""
    if isinstance(obj, dict):
        return {str(k): redact_value(str(k), v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact_payload(item) for item in obj]
    if isinstance(obj, str):
        if "Bearer " in obj:
            prefix, _, _ = obj.partition("Bearer ")
            return f"{prefix}Bearer [REDACTED]"
        if len(obj) > 256:
            return obj[:256] + "...[truncated]"
    return obj


class OperationalTelemetry:
    """Thread-safe structured event log and metrics collector."""

    def __init__(self, max_events: int = 250) -> None:
        self._lock = threading.Lock()
        self._events: deque[dict] = deque(maxlen=max_events)
        self._counters: dict[str, int] = {
            "requests_total": 0,
            "status_2xx": 0,
            "status_4xx": 0,
            "status_5xx": 0,
            "mutations_total": 0,
            "auth_failures_total": 0,
            "csrf_rejections_total": 0,
            "webhook_replays_blocked": 0,
            "provider_errors_total": 0,
            "latency_ms_sum": 0,
            "latency_ms_max": 0,
        }

    def record_request(
        self,
        method: str,
        path: str,
        status: int,
        latency_ms: int,
        *,
        tenant_id: str = "demo",
        actor_id: str = "anonymous",
        role: str = "DEMO",
        trace_id: str | None = None,
        details: dict | None = None,
    ) -> dict:
        tid = trace_id or uuid.uuid4().hex[:16]
        safe_details = redact_payload(details or {})
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": tid,
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "role": role,
            "method": method,
            "path": path,
            "status": status,
            "latency_ms": max(0, int(latency_ms)),
            "details": safe_details,
        }
        with self._lock:
            self._counters["requests_total"] += 1
            if 200 <= status < 300:
                self._counters["status_2xx"] += 1
            elif 400 <= status < 500:
                self._counters["status_4xx"] += 1
            elif status >= 500:
                self._counters["status_5xx"] += 1
            if method == "POST":
                self._counters["mutations_total"] += 1
            if status in (401, 403):
                self._counters["auth_failures_total"] += 1
            self._counters["latency_ms_sum"] += max(0, int(latency_ms))
            if latency_ms > self._counters["latency_ms_max"]:
                self._counters["latency_ms_max"] = int(latency_ms)
            self._events.append(event)

        log_path = os.environ.get("ARCHON_STRUCTURED_LOG_PATH", "").strip()
        if log_path:
            try:
                with open(log_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(event) + "\n")
            except OSError:
                pass
        return event

    def increment(self, counter_name: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[counter_name] = self._counters.get(counter_name, 0) + int(amount)

    def record_security_event(self, event_type: str, details: dict | None = None) -> None:
        with self._lock:
            if "csrf" in event_type:
                self._counters["csrf_rejections_total"] += 1
            elif "replay" in event_type:
                self._counters["webhook_replays_blocked"] += 1
            else:
                self._counters["auth_failures_total"] += 1
            self._events.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "trace_id": uuid.uuid4().hex[:16],
                    "event_type": event_type,
                    "details": redact_payload(details or {}),
                }
            )

    def snapshot(self) -> dict:
        with self._lock:
            total = self._counters["requests_total"]
            avg_ms = (self._counters["latency_ms_sum"] // total) if total > 0 else 0
            return {
                "counters": dict(self._counters),
                "latency_avg_ms": avg_ms,
                "recent_events": list(self._events)[-25:],
                "alerts": self._evaluate_alerts_locked(),
            }

    def _evaluate_alerts_locked(self) -> list[dict]:
        alerts: list[dict] = []
        if self._counters["status_5xx"] > 0:
            alerts.append(
                {
                    "code": "ALERT_HTTP_5XX",
                    "severity": "CRITICAL",
                    "message": f"{self._counters['status_5xx']} server 5xx error(s) observed.",
                }
            )
        if self._counters["webhook_replays_blocked"] > 0:
            alerts.append(
                {
                    "code": "ALERT_WEBHOOK_REPLAY",
                    "severity": "WARNING",
                    "message": f"{self._counters['webhook_replays_blocked']} duplicate webhook replay attempt(s) blocked.",
                }
            )
        if self._counters["csrf_rejections_total"] > 0:
            alerts.append(
                {
                    "code": "ALERT_CSRF_BLOCKED",
                    "severity": "WARNING",
                    "message": f"{self._counters['csrf_rejections_total']} request(s) rejected for missing/invalid CSRF token.",
                }
            )
        return alerts


TELEMETRY = OperationalTelemetry()
