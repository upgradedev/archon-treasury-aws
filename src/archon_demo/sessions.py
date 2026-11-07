"""Per-visitor and per-tenant sessions backed by SQLite WAL durability.

Supports:
- Isolated anonymous demo sessions (one judge cannot move another judge's money).
- Authenticated tenant-scoped operator sessions (READER, EVALUATOR, APPROVER, WRITER, ADMIN).
- Separation of Duties across operators within the same tenant (e.g., Approver approves,
  Writer executes).
- Cold-start recovery and multi-worker state synchronization via PersistenceStore.
- Live tenant isolation (never seeds synthetic demo money into live tenants).
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
import uuid
from dataclasses import dataclass, field

from archon_demo.auth import (
    SessionPrincipal,
    TreasuryRole,
    anonymous_demo_principal,
)
from archon_demo.persistence import PersistenceStore
from archon_demo.service import DemoService

COOKIE_NAME = "archon-session"
MAX_SESSIONS = 128
TTL_SECONDS = 1800


@dataclass(slots=True)
class SessionStore:
    db_path: str | None = None
    _services: dict[str, tuple[DemoService, float, str]] = field(default_factory=dict)
    _principals: dict[str, tuple[SessionPrincipal, float]] = field(default_factory=dict)
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _persistence: PersistenceStore | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        effective_path = self.db_path or os.environ.get("ARCHON_STATE_DB_PATH") or ":memory:"
        self._persistence = PersistenceStore(effective_path)
        self._lock = self._persistence.lock

    def mutation_lock(self) -> threading.RLock:
        return self._lock

    @property
    def persistence(self) -> PersistenceStore:
        assert self._persistence is not None
        return self._persistence

    def resolve(self, session_id: str | None) -> tuple[str, DemoService, bool]:
        """Return (session_id, service, is_new). Unknown or expired ids renew."""
        sid, service, _principal, is_new = self.resolve_with_principal(session_id)
        return sid, service, is_new

    def resolve_with_principal(
        self, session_id: str | None
    ) -> tuple[str, DemoService, SessionPrincipal, bool]:
        """Return (session_id, service, principal, is_new) with cold-start reload."""
        now = time.monotonic()
        with self._lock:
            if session_id:
                existing_p = self._principals.get(session_id)
                if existing_p is not None and now - existing_p[1] <= TTL_SECONDS:
                    principal = existing_p[0]
                    self._principals[session_id] = (principal, now)
                    service = self._load_or_create_tenant_service(principal, now)
                    return session_id, service, principal, False

                persisted_p = self.persistence.load_session(session_id, TTL_SECONDS)
                if persisted_p is not None:
                    self._principals[session_id] = (persisted_p, now)
                    service = self._load_or_create_tenant_service(persisted_p, now)
                    return session_id, service, persisted_p, False

            self._evict(now)
            fresh_id = uuid.uuid4().hex
            principal = anonymous_demo_principal(fresh_id)
            service = DemoService.seeded(tenant_id=principal.tenant_id)
            self._principals[fresh_id] = (principal, now)
            self.persistence.save_session(principal, TTL_SECONDS)
            checksum = self.persistence.save_tenant_state(principal.tenant_id, service.to_persisted_dict())
            self._services[principal.tenant_id] = (service, now, checksum)
            return fresh_id, service, principal, True

    def _load_or_create_tenant_service(self, principal: SessionPrincipal, now: float) -> DemoService:
        tid = principal.tenant_id
        cached = self._services.get(tid)
        db_checksum = self.persistence.get_tenant_checksum(tid)

        if cached is not None and (db_checksum is None or cached[2] == db_checksum):
            self._services[tid] = (cached[0], now, cached[2])
            return cached[0]

        if db_checksum is not None:
            stored = self.persistence.load_tenant_state(tid)
            if stored is not None:
                restored = DemoService.from_persisted_dict(stored)
                if cached is not None:
                    restored.transport = cached[0].transport
                self._services[tid] = (restored, now, db_checksum)
                return restored

        if principal.is_live_tenant:
            service = DemoService.empty_tenant(tid)
        else:
            service = DemoService.seeded(tenant_id=tid)
        checksum = self.persistence.save_tenant_state(tid, service.to_persisted_dict())
        self._services[tid] = (service, now, checksum)
        return service

    def persist(self, session_id: str) -> None:
        """Persist the current tenant state for session_id to SQLite WAL."""
        with self._lock:
            p_entry = self._principals.get(session_id)
            if p_entry is None:
                return
            principal = p_entry[0]
            s_entry = self._services.get(principal.tenant_id)
            if s_entry is None:
                return
            checksum = self.persistence.save_tenant_state(principal.tenant_id, s_entry[0].to_persisted_dict())
            self._services[principal.tenant_id] = (s_entry[0], time.monotonic(), checksum)

    def signup(
        self,
        session_id: str,
        *,
        email: str,
        password: str,
        display_name: str,
        tenant_id: str,
        role: str = "ADMIN",
        separation_of_duties: bool = False,
        is_live_tenant: bool = True,
    ) -> tuple[SessionPrincipal, DemoService]:
        """Register a new operator account and bind the session to that tenant."""
        now = time.monotonic()
        role_enum = TreasuryRole(role.upper())
        with self._lock:
            account = self.persistence.create_user(
                email=email,
                password=password,
                tenant_id=tenant_id,
                display_name=display_name,
                role=role_enum,
                separation_of_duties=separation_of_duties,
                is_live_tenant=is_live_tenant,
            )
            csrf = hashlib.sha256(f"csrf:{session_id}:{account.user_id}".encode("utf-8")).hexdigest()[:32]
            principal = SessionPrincipal(
                session_id=session_id,
                tenant_id=account.tenant_id,
                user_id=account.user_id,
                email=account.email,
                display_name=account.display_name,
                role=account.role,
                csrf_token=csrf,
                authenticated=True,
                separation_of_duties=account.separation_of_duties,
                is_live_tenant=account.is_live_tenant,
            )
            self._principals[session_id] = (principal, now)
            self.persistence.save_session(principal, TTL_SECONDS)
            service = self._load_or_create_tenant_service(principal, now)
            self.persistence.record_audit_event(
                principal.tenant_id,
                principal.user_id,
                "auth.signup",
                {"email": principal.email, "role": principal.role.value, "is_live_tenant": principal.is_live_tenant},
            )
            return principal, service

    def login(
        self,
        session_id: str,
        *,
        email: str,
        password: str,
    ) -> tuple[SessionPrincipal, DemoService]:
        """Authenticate an operator and bind the session to their tenant."""
        now = time.monotonic()
        with self._lock:
            account = self.persistence.authenticate_user(email, password)
            csrf = hashlib.sha256(f"csrf:{session_id}:{account.user_id}".encode("utf-8")).hexdigest()[:32]
            principal = SessionPrincipal(
                session_id=session_id,
                tenant_id=account.tenant_id,
                user_id=account.user_id,
                email=account.email,
                display_name=account.display_name,
                role=account.role,
                csrf_token=csrf,
                authenticated=True,
                separation_of_duties=account.separation_of_duties,
                is_live_tenant=account.is_live_tenant,
            )
            self._principals[session_id] = (principal, now)
            self.persistence.save_session(principal, TTL_SECONDS)
            service = self._load_or_create_tenant_service(principal, now)
            self.persistence.record_audit_event(
                principal.tenant_id,
                principal.user_id,
                "auth.login",
                {"email": principal.email, "role": principal.role.value},
            )
            return principal, service

    def switch_role(
        self,
        session_id: str,
        *,
        role: str,
        user_id: str | None = None,
        separation_of_duties: bool | None = None,
    ) -> SessionPrincipal:
        """Update the active operator role or separation-of-duties policy on the current session."""
        now = time.monotonic()
        role_enum = TreasuryRole(role.upper())
        with self._lock:
            _sid, _svc, current, _new = self.resolve_with_principal(session_id)
            updated = SessionPrincipal(
                session_id=session_id,
                tenant_id=current.tenant_id,
                user_id=user_id.strip() if user_id and user_id.strip() else current.user_id,
                email=current.email,
                display_name=current.display_name,
                role=role_enum,
                csrf_token=current.csrf_token,
                authenticated=current.authenticated,
                separation_of_duties=(
                    bool(separation_of_duties)
                    if separation_of_duties is not None
                    else current.separation_of_duties
                ),
                is_live_tenant=current.is_live_tenant,
            )
            self._principals[session_id] = (updated, now)
            self.persistence.save_session(updated, TTL_SECONDS)
            return updated

    def logout(self, session_id: str) -> SessionPrincipal:
        """Terminate authenticated session and return to an isolated anonymous demo principal."""
        now = time.monotonic()
        with self._lock:
            self.persistence.delete_session(session_id)
            principal = anonymous_demo_principal(session_id)
            service = DemoService.seeded(tenant_id=principal.tenant_id)
            self._principals[session_id] = (principal, now)
            self.persistence.save_session(principal, TTL_SECONDS)
            checksum = self.persistence.save_tenant_state(principal.tenant_id, service.to_persisted_dict())
            self._services[principal.tenant_id] = (service, now, checksum)
            return principal

    def _evict(self, now: float) -> None:
        expired_sids = [sid for sid, (_p, seen) in self._principals.items() if now - seen > TTL_SECONDS]
        for sid in expired_sids:
            del self._principals[sid]
        while len(self._principals) >= MAX_SESSIONS:
            oldest = min(self._principals, key=lambda sid: self._principals[sid][1])
            del self._principals[oldest]

        expired_tids = [tid for tid, (_svc, seen, _chk) in self._services.items() if now - seen > TTL_SECONDS]
        for tid in expired_tids:
            del self._services[tid]
        while len(self._services) >= MAX_SESSIONS:
            oldest_t = min(self._services, key=lambda tid: self._services[tid][1])
            del self._services[oldest_t]

    def active_count(self) -> int:
        with self._lock:
            return len(self._principals)


def parse_cookie(header: str | None) -> str | None:
    if not header:
        return None
    for part in header.split(";"):
        name, _, value = part.strip().partition("=")
        if name == COOKIE_NAME and value:
            return value if len(value) == 32 and all(c in "0123456789abcdef" for c in value) else None
    return None


def cookie_value(session_id: str, secure: bool | None = None) -> str:
    if secure is None:
        secure = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME")) or os.environ.get("ARCHON_COOKIE_SECURE") == "1"
    sec_attr = "; Secure" if secure else ""
    return f"{COOKIE_NAME}={session_id}; Path=/; HttpOnly; SameSite=Lax; Max-Age={TTL_SECONDS}{sec_attr}"
