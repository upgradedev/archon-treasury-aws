"""Judge journey smoke against any deployed base URL. Stdlib only.

Usage: python scripts/smoke_deployed.py https://<function-url>
Runs the exact 60-second story over HTTP and prints one PASS or FAIL line
per step. Exit code 1 on the first failing expectation set. Works against
the local server and the public Lambda URL without changes.
"""

import http.cookiejar
import json
import sys
import urllib.error
import urllib.request

failures = []
OPENER = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
)


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")
    if not ok:
        failures.append(name)


def call(base, method, path, body=None, opener=None, raw=None):
    active = opener or OPENER
    data = raw.encode() if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with active.open(req, timeout=15) as res:
            return res.status, dict(res.getheaders()), res.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), exc.read().decode()


def fresh_opener():
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )


def main(base: str) -> int:
    base = base.rstrip("/")
    status, headers, page = call(base, "GET", "/")
    check("page 200 anonymous", status == 200 and "Archon Treasury" in page, f"HTTP {status}")
    lowered = {k.lower(): v for k, v in headers.items()}
    check("security headers", lowered.get("x-content-type-options") == "nosniff")
    status, _h, body = call(base, "GET", "/healthz")
    check("healthz", status == 200 and json.loads(body)["status"] == "ok")
    status, _h, body = call(base, "GET", "/DEPLOYED_SHA")
    check("deployed sha served", status == 200, body.strip()[:120])
    call(base, "POST", "/api/reset", {})
    for oid in ("obl-usd-1", "obl-eur-1"):
        status, _h, _b = call(base, "POST", f"/api/approve/{oid}", {})
        check(f"approve {oid}", status == 200, f"HTTP {status}")
    status, _h, body = call(base, "POST", "/api/simulate-deposit", {"currency": "EUR", "amount": "500.00"})
    outcome = json.loads(body) if status == 200 else {}
    check("EUR deposit invalidates only EUR",
          outcome.get("invalidated") == ["obl-eur-1"] and outcome.get("still_valid") == ["obl-usd-1"],
          json.dumps(outcome)[:160])
    status, _h, _b = call(base, "POST", "/api/execute/obl-usd-1", {})
    check("valid USD executes", status == 200, f"HTTP {status}")
    status, _h, body = call(base, "POST", "/api/execute/obl-eur-1", {})
    check("stale EUR refused 409", status == 409 and "stale" in body, f"HTTP {status}")
    status, _h, body = call(base, "GET", "/api/state")
    state = json.loads(body) if status == 200 else {}
    check("exactly one transfer", state.get("transfer_count") == 1, f"count={state.get('transfer_count')}")
    rules = {f["rule_id"] for f in state.get("findings", [])}
    check("seeded findings R01, R02, R09, and live R18 visible", {"R01", "R02", "R09", "R18"} <= rules, f"rules={sorted(rules)}")
    # Recovery: re-approve the EUR payout on the new evidence, then it pays.
    status, _h, _b = call(base, "POST", "/api/approve/obl-eur-1", {})
    check("re-approve after invalidation", status == 200, f"HTTP {status}")
    status, _h, body = call(base, "GET", "/api/state")
    rules_after = {f["rule_id"] for f in (json.loads(body) if status == 200 else {}).get("findings", [])}
    check("R18 clears after re-approval", "R18" not in rules_after, f"rules={sorted(rules_after)}")
    status, _h, _b = call(base, "POST", "/api/execute/obl-eur-1", {})
    check("recovered EUR executes", status == 200, f"HTTP {status}")
    # Metal x402 USDZ sub-agent spend governor live checks.
    status, _h, body = call(base, "POST", "/api/metal-call/agent-fx", {})
    check("metal x402 sub-agent call", status == 200 and json.loads(body).get("calls_used") == 1, f"HTTP {status}")
    status, _h, body = call(base, "POST", "/api/metal-rebalance", {"agent_id": "agent-fx", "new_price": "0.50"})
    changes = json.loads(body).get("changes", []) if status == 200 else []
    check("metal x402 price spike shrinks cap 200->100", status == 200 and changes and changes[0].get("new_call_cap") == 100, f"HTTP {status}")
    status, _h, body = call(base, "POST", "/api/metal-mandate", {"agent_id": "agent-fx", "new_max_price_cents": 60})
    check("metal x402 mandate replacement", status == 200 and json.loads(body).get("new_max_price_cents") == 60, f"HTTP {status}")
    status, _h, body = call(base, "POST", "/api/metal-dispute", {})
    check("metal x402 signed-order dispute refund", status == 200 and json.loads(body).get("refunded_cents") == 5, f"HTTP {status}")
    status, _h, body = call(base, "POST", "/api/customer-email", {"contradicts": True})
    check("kit1 contradicting customer email lowers confidence", status == 200 and json.loads(body).get("confidence_pct") == 35, f"HTTP {status}")
    status, _h, body = call(base, "POST", "/api/evaluate-invoice", {"obligation_id": "obl-usd-1", "mode": "matching"})
    check("evaluator valid invoice proposed", status == 200 and json.loads(body).get("verdict") == "PROPOSED", f"HTTP {status}")
    status, _h, body = call(base, "POST", "/api/evaluate-invoice", {"obligation_id": "obl-usd-1", "mode": "mismatched"})
    check("evaluator tampered invoice refused", status == 200 and json.loads(body).get("verdict") == "REFUSED", f"HTTP {status}")
    status, _h, body = call(base, "POST", "/api/incident-fail", {"failure_type": "bank_return"})
    check("kit3 incident transitions SENT to CANCELLED", status == 200 and json.loads(body).get("status") == "CANCELLED", f"HTTP {status}")
    status, _h, body = call(base, "POST", "/api/incident-resolve", {})
    check("kit3 incident issues replacement under duplicate lock", status == 200 and json.loads(body).get("decision") == "REPLACE", f"HTTP {status}")
    # Reserve-floor refusal and recovery on obl-usd-2 ($1,650.00 against $2,050.00 balance and $500.00 floor).
    status, _h, _b = call(base, "POST", "/api/approve/obl-usd-2", {})
    check("approve obl-usd-2 before floor check", status == 200, f"HTTP {status}")
    status, _h, body = call(base, "POST", "/api/execute/obl-usd-2", {})
    check("reserve floor breach refused 409", status == 409 and "reserve floor" in body, f"HTTP {status}")
    status, _h, _b = call(base, "POST", "/api/simulate-deposit", {"currency": "USD", "amount": "200.00"})
    check("USD deposit restores reserve floor", status == 200, f"HTTP {status}")
    status, _h, _b = call(base, "POST", "/api/approve/obl-usd-2", {})
    check("re-approve obl-usd-2 after USD deposit", status == 200, f"HTTP {status}")
    status, _h, _b = call(base, "POST", "/api/execute/obl-usd-2", {})
    check("obl-usd-2 executes above reserve floor", status == 200, f"HTTP {status}")
    # Hostile and mistaken inputs stay polite.
    status, _h, _b = call(base, "POST", "/api/simulate-deposit", raw="{bad")
    check("bad JSON is 400", status == 400, f"HTTP {status}")
    status, _h, _b = call(base, "POST", "/api/simulate-deposit", raw="[]")
    check("non-object JSON is 400", status == 400, f"HTTP {status}")
    status, _h, _b = call(base, "POST", "/api/simulate-deposit", {})
    check("missing fields is 400", status == 400, f"HTTP {status}")
    status, _h, _b = call(base, "POST", "/api/simulate-deposit", {"currency": "EUR", "amount": "-500.00"})
    check("negative deposit is 409", status == 409, f"HTTP {status}")
    status, _h, _b = call(base, "POST", "/api/simulate-deposit", {"currency": "EUR", "amount": "0.00"})
    check("zero deposit is 409", status == 409, f"HTTP {status}")
    status, _h, _b = call(base, "POST", "/api/simulate-deposit", raw='{"pad":"' + ("x" * 17000) + '"}')
    check("oversized body is 413", status == 413, f"HTTP {status}")
    status, _h, _b = call(base, "POST", "/api/approve/obl-nope", {})
    check("unknown obligation is 409", status == 409, f"HTTP {status}")
    status, _h, _b = call(base, "POST", "/api/execute/obl-gbp-1", {})
    check("execute without approval is 409", status == 409, f"HTTP {status}")
    status, _h, _b = call(base, "GET", "/favicon.ico")
    check("favicon is 204", status == 204, f"HTTP {status}")
    # A second visitor must see a pristine demo.
    other = fresh_opener()
    status, _h, body = call(base, "GET", "/api/state", opener=other)
    other_state = json.loads(body) if status == 200 else {}
    check("second visitor isolated", other_state.get("transfer_count") == 0,
          f"count={other_state.get('transfer_count')}")
    print(f"SMOKE {'PASS' if not failures else 'FAIL'} base={base} failed={failures or 'none'}")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
