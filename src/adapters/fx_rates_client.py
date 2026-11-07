"""Live European Central Bank (ECB) FX Reference Rate Adapter.

Fetches real daily institutional reference exchange rates (EUR/USD, EUR/GBP,
GBP/USD) from the public ECB feed (api.frankfurter.app) over HTTPS using stdlib
urllib, converting rates via Decimal into integer basis points (10,000 = 1.0000).
Caches the response for 15 minutes per process and falls back deterministically
when offline (so unit tests never touch the network unless enabled).
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from decimal import Decimal, ROUND_HALF_UP

_CACHE_TTL_SECONDS = 900.0
_cached_rates: dict | None = None
_cached_at: float = 0.0

ECB_ENDPOINT = "https://api.frankfurter.app/latest?from=EUR&to=USD,GBP"


def _to_bps(val: object) -> int:
    d = Decimal(str(val))
    return int((d * Decimal(10_000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def reset_fx_cache() -> None:
    global _cached_rates, _cached_at
    _cached_rates = None
    _cached_at = 0.0


def get_fx_rates(allow_network: bool | None = None, endpoint: str = ECB_ENDPOINT) -> dict:
    """Return live ECB FX reference rates (in integer bps and major strings)."""
    global _cached_rates, _cached_at
    if allow_network is None:
        allow_network = (
            os.environ.get("ARCHON_ENABLE_LIVE_FX") == "1"
            or os.environ.get("ARCHON_ENABLE_LIVE_AIRWALLEX") == "1"
            or os.environ.get("ARCHON_ENABLE_LIVE_BEDROCK") == "1"
            or bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
        )

    now = time.monotonic()
    if _cached_rates is not None and (now - _cached_at) < _CACHE_TTL_SECONDS:
        return _cached_rates

    if allow_network:
        try:
            req = urllib.request.Request(
                endpoint,
                headers={"Accept": "application/json", "User-Agent": "ArchonTreasury/1.0"},
            )
            with urllib.request.urlopen(req, timeout=2.0) as res:
                payload = json.loads(res.read().decode("utf-8"))
            rates = payload.get("rates") or {}
            eur_usd_bps = _to_bps(rates["USD"])
            eur_gbp_bps = _to_bps(rates["GBP"])
            gbp_usd_bps = (eur_usd_bps * 10_000) // max(1, eur_gbp_bps)
            result = {
                "source": "ecb-reference-rates-live",
                "as_of_date": str(payload.get("date", "live")),
                "eur_usd_bps": eur_usd_bps,
                "eur_gbp_bps": eur_gbp_bps,
                "gbp_usd_bps": gbp_usd_bps,
                "eur_usd": f"{eur_usd_bps // 10_000}.{eur_usd_bps % 10_000:04d}",
                "eur_gbp": f"{eur_gbp_bps // 10_000}.{eur_gbp_bps % 10_000:04d}",
                "gbp_usd": f"{gbp_usd_bps // 10_000}.{gbp_usd_bps % 10_000:04d}",
            }
            _cached_rates = result
            _cached_at = now
            return result
        except Exception:
            pass

    return {
        "source": "ecb-reference-rates-pinned-offline",
        "as_of_date": "2026-11-05",
        "eur_usd_bps": 10845,
        "eur_gbp_bps": 8390,
        "gbp_usd_bps": 12926,
        "eur_usd": "1.0845",
        "eur_gbp": "0.8390",
        "gbp_usd": "1.2926",
    }
