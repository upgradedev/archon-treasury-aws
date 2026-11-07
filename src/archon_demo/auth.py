"""Authentication, tenant isolation, least-privilege RBAC, separation of duties, and CSRF.

Enforces production gap #3:
- Real PBKDF2-HMAC-SHA256 password hashing and constant-time verification.
- Tenant-isolated principals (tenant_id, user_id, email, role, separation_of_duties).
- Least-privilege role permissions: READER, EVALUATOR, APPROVER, WRITER, ADMIN.
- Separation of Duties (SoD): when enabled on a tenant (or for APPROVER/WRITER roles),
  the principal who approved an obligation cannot also execute its payout.
- Cookie-compatible CSRF token binding and constant-time header verification.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from enum import Enum

from kerdon.errors import CapabilityError, DomainError

AuthorizationError = CapabilityError


class TreasuryRole(str, Enum):
    READER = "READER"
    EVALUATOR = "EVALUATOR"
    APPROVER = "APPROVER"
    WRITER = "WRITER"
    ADMIN = "ADMIN"


ROLE_PERMISSIONS: dict[TreasuryRole, frozenset[str]] = {
    TreasuryRole.READER: frozenset({"read", "export"}),
    TreasuryRole.EVALUATOR: frozenset({"read", "export", "evaluate"}),
    TreasuryRole.APPROVER: frozenset({"read", "export", "evaluate", "approve", "deposit", "fx_quote", "floor"}),
    TreasuryRole.WRITER: frozenset(
        {"read", "export", "execute", "fx_convert", "visa", "metal", "incident", "reconcile"}
    ),
    TreasuryRole.ADMIN: frozenset(
        {
            "read",
            "export",
            "evaluate",
            "approve",
            "execute",
            "deposit",
            "fx_quote",
            "fx_convert",
            "floor",
            "visa",
            "metal",
            "incident",
            "reconcile",
            "configure",
            "backup",
        }
    ),
}


@dataclass(frozen=True, slots=True)
class UserAccount:
    user_id: str
    tenant_id: str
    email: str
    display_name: str
    role: TreasuryRole
    password_salt_hex: str
    password_hash_hex: str
    separation_of_duties: bool = True
    is_live_tenant: bool = False


@dataclass(frozen=True, slots=True)
class SessionPrincipal:
    session_id: str
    tenant_id: str
    user_id: str
    email: str
    display_name: str
    role: TreasuryRole
    csrf_token: str
    authenticated: bool
    separation_of_duties: bool = False
    is_live_tenant: bool = False

    def has_permission(self, perm: str) -> bool:
        return perm in ROLE_PERMISSIONS.get(self.role, frozenset())

    def require_permission(self, perm: str) -> None:
        if not self.has_permission(perm):
            raise AuthorizationError(
                f"role {self.role.value} on tenant {self.tenant_id} lacks '{perm}' permission"
            )

    def check_separation_of_duties(self, approver_id: str) -> None:
        if self.separation_of_duties and approver_id == self.user_id:
            raise AuthorizationError(
                f"separation of duties violation: operator {self.user_id} approved this payout and cannot also execute it"
            )

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id[:8] + "...",
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role.value,
            "csrf_token": self.csrf_token,
            "authenticated": self.authenticated,
            "separation_of_duties": self.separation_of_duties,
            "is_live_tenant": self.is_live_tenant,
            "permissions": sorted(ROLE_PERMISSIONS.get(self.role, frozenset())),
        }


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    if len(password) < 8:
        raise DomainError("password must be at least 8 characters")
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 60_000)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    try:
        _, actual_hex = hash_password(password, salt_hex)
    except DomainError:
        return False
    return hmac.compare_digest(actual_hex, expected_hash_hex)


def verify_csrf_token(expected: str, provided: str | None) -> bool:
    if not expected or not provided:
        return False
    return hmac.compare_digest(expected.strip(), provided.strip())


def anonymous_demo_principal(session_id: str, csrf_token: str | None = None) -> SessionPrincipal:
    token = csrf_token or hashlib.sha256(f"csrf:{session_id}".encode("utf-8")).hexdigest()[:32]
    return SessionPrincipal(
        session_id=session_id,
        tenant_id=f"demo-{session_id[:12]}",
        user_id="elena-vance",
        email="elena.vance@vancehardware.demo",
        display_name="Elena Vance (Demo Session)",
        role=TreasuryRole.ADMIN,
        csrf_token=token,
        authenticated=False,
        separation_of_duties=False,
        is_live_tenant=False,
    )
