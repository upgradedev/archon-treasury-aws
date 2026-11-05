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
from dataclasses import dataclass, field

from adapters.airwallex_client import AdapterError, DuplicateRequestError

DEFAULT_BASE_URL = "https://api.sandbox.airwallex.com"


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

    def _raw(self, method: str, path: str, payload: dict | None, headers: dict) -> dict:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
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
        return self._raw(method, path, payload, {"Authorization": f"Bearer {token}"})
