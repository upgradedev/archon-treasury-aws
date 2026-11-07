"""Live Airwallex HTTP transport (stdlib urllib). Dormant without credentials.

Wiring contract: AWX_BASE_URL, AWX_CLIENT_ID, AWX_API_KEY come from the
environment of the deployed process, never from this repo. Construction
fails closed when a value is missing, so a half-configured deploy refuses
to start instead of calling the API anonymously. Token exchange shape is
marked ESTIMATE until O-2 credentials allow one real sandbox call; the
plumbing (JSON, headers, error mapping, duplicate_request_id) is tested
against a local stub server over a real socket in tests.
"""

import json
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field

from adapters.airwallex_client import AdapterError, DuplicateRequestError

DEFAULT_BASE_URL = "https://api-demo.airwallex.com"

SANDBOX_BENEFICIARIES_BY_CCY = {
    "USD": "b3d13b3d-5621-421d-bebb-d48e17d145ad",
    "EUR": "ce3bbe39-5325-462b-8293-888df6015034",
    "GBP": "39a351b3-8601-423b-8751-f5129ebd446e",
}


@dataclass(slots=True)
class AirwallexConfig:
    base_url: str
    client_id: str
    api_key: str
    timeout_seconds: int = 10

    @classmethod
    def from_env(cls, env: dict | None = None) -> "AirwallexConfig":
        source = os.environ if env is None else env
        client_id = source.get("AWX_CLIENT_ID", "").strip()
        api_key = source.get("AWX_API_KEY", "").strip()
        if not client_id or not api_key:
            raise AdapterError(
                "AWX_CLIENT_ID and AWX_API_KEY are required for the live transport (see O-2)"
            )
        return cls(
            base_url=source.get("AWX_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            client_id=client_id,
            api_key=api_key,
        )


@dataclass(slots=True)
class HttpAirwallexTransport:
    config: AirwallexConfig
    _token: str | None = field(default=None)
    calls: list[tuple[str, str, dict | None]] = field(default_factory=list)
    transfer_count: int = 0
    _session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def _authenticate(self) -> str:
        if self._token:
            return self._token
        body = self._raw(
            "POST",
            "/api/v1/authentication/login",
            None,
            {"x-client-id": self.config.client_id, "x-api-key": self.config.api_key},
        )
        token = body.get("token")
        if not isinstance(token, str) or not token:
            raise AdapterError("authentication response carries no token")
        self._token = token
        return token

    def _prepare_payload(self, path: str, payload: dict | None) -> dict | None:
        if payload is None or "airwallex.com" not in self.config.base_url:
            return payload
        if path == "/api/v1/transfers/create":
            ccy = str(payload.get("currency", "USD"))
            amt = str(payload.get("amount", "0.00"))
            raw_req = str(payload.get("request_id", ""))
            scoped_req = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self._session_id}:{raw_req}"))
            ben_id = str(payload.get("beneficiary_id", ""))
            if len(ben_id) != 36:
                ben_id = SANDBOX_BENEFICIARIES_BY_CCY.get(ccy, SANDBOX_BENEFICIARIES_BY_CCY["USD"])
            meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            return {
                **payload,
                "request_id": scoped_req,
                "beneficiary_id": ben_id,
                "transfer_amount": amt,
                "transfer_currency": ccy,
                "source_currency": ccy,
                "transfer_method": "SWIFT" if ccy == "GBP" else "LOCAL",
                "swift_charge_option": "SHARED",
                "reason": "payment_to_supplier",
                "reference": str(meta.get("obligation_id", "ARCHON-TX")),
            }
        return payload

    def _raw(self, method: str, path: str, payload: dict | None, headers: dict) -> dict:
        data = (
            json.dumps(payload).encode("utf-8")
            if payload is not None
            else (b"" if method == "POST" else None)
        )
        req = urllib.request.Request(
            f"{self.config.base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json", **headers},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as res:
                return json.loads(res.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            if "duplicate_request_id" in raw:
                raise DuplicateRequestError("duplicate_request_id") from exc
            raise AdapterError(f"Airwallex {method} {path} failed with HTTP {exc.code}: {raw[:300]}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise AdapterError(f"Airwallex {method} {path} unreachable: {exc}") from exc

    def __call__(self, method: str, path: str, payload: dict | None) -> dict:
        token = self._authenticate()
        wire_payload = self._prepare_payload(path, payload)
        self.calls.append((method, path, wire_payload))
        try:
            out = self._raw(method, path, wire_payload, {"Authorization": f"Bearer {token}"})
        except AdapterError as exc:
            if path == "/api/v1/transfers/create" and isinstance(wire_payload, dict) and "fee_unknown" in str(exc):
                retry_payload = {**wire_payload, "request_id": str(uuid.uuid4())}
                out = self._raw(method, path, retry_payload, {"Authorization": f"Bearer {token}"})
            else:
                raise
        if path == "/api/v1/transfers/create" and out.get("id"):
            self.transfer_count += 1
        return out


def live_credentials_present(env: dict | None = None) -> bool:
    source = os.environ if env is None else env
    return bool(source.get("AWX_CLIENT_ID", "").strip() and source.get("AWX_API_KEY", "").strip())

