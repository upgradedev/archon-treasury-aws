"""Per-visitor demo sessions. One judge cannot move another judge's money.

UAT finding (2026-11-05): the first deployed build kept one global demo
state, so two anonymous visitors shared approvals and a reset wiped the
other visitor mid-story. Sessions fix that with an opaque cookie. State
still lives in memory per process (per Lambda container), is capped, and
expires; the page says demo state is per visitor and resets often.
"""

import threading
import time
import uuid
from dataclasses import dataclass, field

from archon_demo.service import DemoService

COOKIE_NAME = "archon-session"
MAX_SESSIONS = 128
TTL_SECONDS = 1800


@dataclass(slots=True)
class SessionStore:
    _services: dict[str, tuple[DemoService, float]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def resolve(self, session_id: str | None) -> tuple[str, DemoService, bool]:
        """Return (session_id, service, is_new). Unknown or expired ids renew."""
        now = time.monotonic()
        with self._lock:
            if session_id:
                existing = self._services.get(session_id)
                if existing is not None and now - existing[1] <= TTL_SECONDS:
                    self._services[session_id] = (existing[0], now)
                    return session_id, existing[0], False
            self._evict(now)
            fresh_id = uuid.uuid4().hex
            service = DemoService.seeded()
            self._services[fresh_id] = (service, now)
            return fresh_id, service, True

    def _evict(self, now: float) -> None:
        expired = [sid for sid, (_svc, seen) in self._services.items() if now - seen > TTL_SECONDS]
        for sid in expired:
            del self._services[sid]
        while len(self._services) >= MAX_SESSIONS:
            oldest = min(self._services, key=lambda sid: self._services[sid][1])
            del self._services[oldest]

    def active_count(self) -> int:
        with self._lock:
            return len(self._services)


def parse_cookie(header: str | None) -> str | None:
    if not header:
        return None
    for part in header.split(";"):
        name, _, value = part.strip().partition("=")
        if name == COOKIE_NAME and value:
            # Session ids we mint are uuid4 hex; anything else is not ours.
            return value if len(value) == 32 and all(c in "0123456789abcdef" for c in value) else None
    return None


def cookie_value(session_id: str) -> str:
    return f"{COOKIE_NAME}={session_id}; Path=/; HttpOnly; SameSite=Lax; Max-Age={TTL_SECONDS}"
