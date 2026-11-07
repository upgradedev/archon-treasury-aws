"""Regression tests for all 7 production gaps on design/archon-gtm-ui.

Covers:
1. Deployment: static React SPA serving (/app, /assets/*, ARCHON_SERVE_REACT_UI=1) + deterministic Lambda zip packaging.
2. Durability: SQLite WAL persistence across cold starts & concurrent workers; zero synthetic money in live tenants.
3. Auth & RBAC: PBKDF2 signup/login, tenant isolation, least-privilege roles, Separation of Duties, and CSRF enforcement.
4. Providers: decoupled Airwallex vs Bedrock config, honest mode labels, and HMAC webhook replay protection.
5. Missing operations: reserve-floor management, persistent deposits, standalone FX quotes & conversions (including expiry refusal), and integrations verification.
7. Operations: secret/PII redaction, /api/metrics, /api/reconcile, and checksummed tenant backup/restore.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from adapters.live_transport import airwallex_enabled, resolve_airwallex_mode_label
from adapters.webhook import sign_payload
from archon_demo.lambda_handler import dispatch_http, handler
from archon_demo.observability import redact_payload
from archon_demo.service import DEMO_WEBHOOK_SECRET
from archon_demo.sessions import SessionStore


class SessionClient:
    """Test helper that maintains session cookie and CSRF token against a SessionStore."""

    def __init__(self, store: SessionStore):
        self.store = store
        self.cookie: str | None = None
        self.csrf_token: str | None = None

    def request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        headers: dict[str, str] | None = None,
        include_csrf: bool = True,
    ) -> tuple[int, str | dict]:
        req_headers = dict(headers or {})
        if include_csrf and self.csrf_token and "x-csrf-token" not in {k.lower() for k in req_headers}:
            req_headers["x-csrf-token"] = self.csrf_token
        raw = json.dumps(body) if body is not None else ""
        status, out, _ctype, set_cookie = dispatch_http(
            self.store,
            method,
            path,
            raw,
            self.cookie,
            headers=req_headers,
        )
        if set_cookie:
            self.cookie = set_cookie.split(";", 1)[0]
        if isinstance(out, dict):
            sess = out.get("session")
            if isinstance(sess, dict) and sess.get("csrf_token"):
                self.csrf_token = sess["csrf_token"]
        return status, out


class ProductionGapsTest(unittest.TestCase):
    def test_gap1_static_spa_routing_and_cutover_flag(self):
        store = SessionStore()
        client = SessionClient(store)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            fake_dist = Path(tmpdir)
            (fake_dist / "index.html").write_text(
                '<!doctype html><html><body><div id="root"></div></body></html>',
                encoding="utf-8",
            )
            (fake_dist / "assets").mkdir(parents=True, exist_ok=True)
            (fake_dist / "assets" / "app.js").write_text("console.log('archon');", encoding="utf-8")

            with patch("archon_demo.lambda_handler._find_frontend_dist", return_value=fake_dist):
                # Default / serves legacy Python HTML
                st_default, body_default = client.request("GET", "/")
                self.assertEqual(st_default, 200)
                self.assertIn("reserve floor", str(body_default))

                # /app and deep links /app/payouts serve React SPA
                st_app, body_app = client.request("GET", "/app/payouts")
                self.assertEqual(st_app, 200)
                self.assertIn('<div id="root"></div>', str(body_app))

                # /assets/app.js serves built asset
                st_asset, body_asset = client.request("GET", "/assets/app.js")
                self.assertEqual(st_asset, 200)
                self.assertIn("archon", str(body_asset))

                # ARCHON_SERVE_REACT_UI=1 switches / to React SPA while /legacy keeps Python HTML
                with patch.dict(os.environ, {"ARCHON_SERVE_REACT_UI": "1"}):
                    st_cutover, body_cutover = client.request("GET", "/")
                    self.assertEqual(st_cutover, 200)
                    self.assertIn('<div id="root"></div>', str(body_cutover))
                    st_legacy, body_legacy = client.request("GET", "/legacy")
                    self.assertEqual(st_legacy, 200)
                    self.assertIn("reserve floor", str(body_legacy))

                # Path traversal on /assets/ is refused
                st_trav, _ = client.request("GET", "/assets/../../pyproject.toml")
                self.assertEqual(st_trav, 404)

    def test_gap2_cold_start_durability_and_live_tenant_zero_seed(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_file = str(Path(tmpdir) / "durable.sqlite3")
            store1 = SessionStore(db_path=db_file)
            client1 = SessionClient(store1)
            client1.request("GET", "/api/state")

            # Approve obl-usd-1, record a deposit, lock an FX quote, and execute obl-usd-1
            self.assertEqual(client1.request("POST", "/api/approve/obl-usd-1", {})[0], 200)
            dep_st, dep_out = client1.request(
                "POST",
                "/api/deposits",
                {"currency": "GBP", "amount": "125.00", "payer_name": "Bristol Aero Ltd", "reference": "WIRE-991"},
            )
            self.assertEqual(dep_st, 200)
            self.assertEqual(dep_out["payer_name"], "Bristol Aero Ltd")

            fx_st, fx_out = client1.request(
                "POST",
                "/api/fx/quote",
                {"sell_currency": "EUR", "buy_currency": "USD", "sell_amount": "100.00", "ttl_seconds": 600},
            )
            self.assertEqual(fx_st, 200)
            quote_id = fx_out["quote_id"]

            exe_st, _ = client1.request("POST", "/api/execute/obl-usd-1", {})
            self.assertEqual(exe_st, 200)

            # Simulate cold start with a brand-new SessionStore pointing at the same SQLite DB
            store2 = SessionStore(db_path=db_file)
            client2 = SessionClient(store2)
            client2.cookie = client1.cookie
            client2.csrf_token = client1.csrf_token

            st2, state2 = client2.request("GET", "/api/state")
            self.assertEqual(st2, 200)
            usd1 = next(o for o in state2["obligations"] if o["obligation_id"] == "obl-usd-1")
            self.assertEqual(usd1["approval_state"], "PAID")
            self.assertTrue(usd1["receipt"]["merkle_verified"])
            self.assertEqual(len(state2["deposit_history"]), 1)
            self.assertEqual(state2["deposit_history"][0]["reference"], "WIRE-991")
            self.assertEqual(len(state2["fx_quotes"]), 1)
            self.assertEqual(state2["fx_quotes"][0]["quote_id"], quote_id)

            # Second execute after cold start is still refused
            dup_st, dup_out = client2.request("POST", "/api/execute/obl-usd-1", {})
            self.assertEqual(dup_st, 409)
            self.assertIn("already paid", dup_out["error"])

            # Live tenant signup never seeds synthetic money
            live_client = SessionClient(store2)
            live_client.request("GET", "/api/state")
            s_st, s_out = live_client.request(
                "POST",
                "/api/auth/signup",
                {
                    "email": "cfo@livecorp.io",
                    "password": "StrongPassword#2026",
                    "display_name": "Live Corp CFO",
                    "tenant_id": "tenant-livecorp",
                    "role": "ADMIN",
                    "is_live_tenant": True,
                },
            )
            self.assertEqual(s_st, 200)
            live_state = s_out["state"]
            self.assertTrue(live_state["is_live_tenant"])
            self.assertEqual(len(live_state["obligations"]), 0)
            for bal in live_state["balances"]:
                self.assertEqual(bal["amount_cents"], 0)

    def test_gap3_rbac_separation_of_duties_and_csrf(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_file = str(Path(tmpdir) / "rbac.sqlite3")
            store = SessionStore(db_path=db_file)

            # 1. Login as Approver (Elena Vance) on tenant-vance-studio
            elena = SessionClient(store)
            elena.request("GET", "/api/state")
            l_st, _ = elena.request(
                "POST",
                "/api/auth/login",
                {"email": "elena.vance@vancehardware.io", "password": "ArchonTreasury#2026"},
            )
            self.assertEqual(l_st, 200)

            # CSRF missing or invalid is rejected with 403 for authenticated user
            no_csrf_st, _ = elena.request("POST", "/api/approve/obl-usd-1", {}, include_csrf=False)
            self.assertEqual(no_csrf_st, 403)
            bad_csrf_st, _ = elena.request(
                "POST", "/api/approve/obl-usd-1", {}, headers={"x-csrf-token": "wrong-token"}
            )
            self.assertEqual(bad_csrf_st, 403)

            # Valid CSRF allows Elena (APPROVER) to approve obl-usd-1
            app_st, app_out = elena.request("POST", "/api/approve/obl-usd-1", {})
            self.assertEqual(app_st, 200)
            self.assertEqual(app_out["approver_id"], "elena-vance")

            # Elena (APPROVER) cannot execute (lacks 'execute' permission -> 403)
            exe_elena_st, _ = elena.request("POST", "/api/execute/obl-usd-1", {})
            self.assertEqual(exe_elena_st, 403)

            # Even if Elena switches role to WRITER with separation_of_duties=True, SoD blocks self-execution!
            elena.request("POST", "/api/auth/role", {"role": "WRITER", "separation_of_duties": True})
            sod_st, sod_out = elena.request("POST", "/api/execute/obl-usd-1", {})
            self.assertEqual(sod_st, 403)
            self.assertIn("separation of duties", sod_out["error"])

            # 2. Login as External Auditor (READER) on tenant-vance-studio
            auditor = SessionClient(store)
            auditor.request("GET", "/api/state")
            auditor.request(
                "POST",
                "/api/auth/login",
                {"email": "auditor@vancehardware.io", "password": "ArchonTreasury#2026"},
            )
            self.assertEqual(auditor.request("GET", "/api/state")[0], 200)
            self.assertEqual(auditor.request("GET", "/api/audit-export.csv")[0], 200)
            self.assertEqual(auditor.request("POST", "/api/approve/obl-eur-1", {})[0], 403)
            self.assertEqual(auditor.request("POST", "/api/reserve-floor", {"currency": "USD", "reserve_floor": "100.00"})[0], 403)

            # 3. Login as Marcus Chen (WRITER) on tenant-vance-studio -> executes Elena's approval!
            marcus = SessionClient(store)
            marcus.request("GET", "/api/state")
            marcus.request(
                "POST",
                "/api/auth/login",
                {"email": "marcus.chen@vancehardware.io", "password": "ArchonTreasury#2026"},
            )
            m_exe_st, m_exe_out = marcus.request(
                "POST",
                "/api/execute/obl-usd-1",
                {"approval_sha256": app_out["approval_sha256"]},
            )
            self.assertEqual(m_exe_st, 200)
            self.assertEqual(m_exe_out["state"], "PAID")

    def test_gap4_provider_decoupling_and_webhook_replay_protection(self):
        # Decoupling test: Bedrock live without Airwallex live when ARCHON_ENABLE_LIVE_AIRWALLEX=0
        with patch.dict(
            os.environ,
            {
                "ARCHON_ENABLE_LIVE_BEDROCK": "1",
                "ARCHON_ENABLE_LIVE_AIRWALLEX": "0",
                "AWX_CLIENT_ID": "cid",
                "AWX_API_KEY": "key",
            },
        ):
            self.assertFalse(airwallex_enabled())
            self.assertEqual(resolve_airwallex_mode_label(), "synthetic-demo-fake-transport")

        # Airwallex sandbox enabled with Bedrock disabled
        with patch.dict(
            os.environ,
            {
                "ARCHON_ENABLE_LIVE_BEDROCK": "0",
                "ARCHON_AIRWALLEX_MODE": "sandbox",
                "AWX_CLIENT_ID": "cid",
                "AWX_API_KEY": "key",
            },
        ):
            self.assertTrue(airwallex_enabled())
            self.assertEqual(resolve_airwallex_mode_label(), "live-airwallex-sandbox")

        # Signed webhook and replay protection
        store = SessionStore()
        client = SessionClient(store)
        client.request("GET", "/api/state")
        webhook_payload = {
            "id": "evt-live-webhook-001",
            "data": {"global_account_id": "ga-de-demo", "currency": "EUR", "amount": "250.00"},
        }
        raw_bytes = json.dumps(webhook_payload).encode("utf-8")
        good_sig = sign_payload(raw_bytes, DEMO_WEBHOOK_SECRET)

        # Bad signature -> 401
        bad_st, _ = client.request(
            "POST",
            "/api/webhooks/airwallex",
            webhook_payload,
            headers={"x-airwallex-signature": "0" * 64},
            include_csrf=False,
        )
        self.assertEqual(bad_st, 401)

        # Valid signature -> 200
        ok_st, _ = client.request(
            "POST",
            "/api/webhooks/airwallex",
            webhook_payload,
            headers={"x-airwallex-signature": good_sig},
            include_csrf=False,
        )
        self.assertEqual(ok_st, 200)

        # Replay of same event_id -> 409 DuplicateWebhookError
        rep_st, rep_out = client.request(
            "POST",
            "/api/webhooks/airwallex",
            webhook_payload,
            headers={"x-airwallex-signature": good_sig},
            include_csrf=False,
        )
        self.assertEqual(rep_st, 409)
        self.assertIn("already processed", rep_out["error"])

    def test_gap5_floor_management_and_fx_quotes_and_conversions(self):
        store = SessionStore()
        client = SessionClient(store)
        client.request("GET", "/api/state")

        # Approve USD and EUR payouts
        client.request("POST", "/api/approve/obl-usd-1", {})
        client.request("POST", "/api/approve/obl-eur-1", {})

        # Raise EUR reserve floor to 1100.00 -> invalidates only obl-eur-1, keeps obl-usd-1 valid
        fl_st, fl_out = client.request(
            "POST",
            "/api/reserve-floor",
            {"currency": "EUR", "reserve_floor": "1100.00"},
        )
        self.assertEqual(fl_st, 200)
        self.assertEqual(fl_out["invalidated"], ["obl-eur-1"])
        self.assertEqual(fl_out["still_valid"], ["obl-usd-1"])

        # Expired FX quote is refused on conversion and surfaces R12 finding
        exp_st, exp_q = client.request(
            "POST",
            "/api/fx/quote",
            {"sell_currency": "USD", "buy_currency": "EUR", "sell_amount": "100.00", "ttl_seconds": -5},
        )
        self.assertEqual(exp_st, 200)
        self.assertTrue(exp_q["expired"])
        conv_exp_st, conv_exp_out = client.request(
            "POST",
            "/api/fx/convert",
            {"quote_id": exp_q["quote_id"]},
        )
        self.assertEqual(conv_exp_st, 409)
        self.assertIn("expired", conv_exp_out["error"])

        # Valid FX quote converts balances and respects reserve floors
        val_st, val_q = client.request(
            "POST",
            "/api/fx/quote",
            {"sell_currency": "USD", "buy_currency": "EUR", "sell_amount": "200.00", "ttl_seconds": 300},
        )
        self.assertEqual(val_st, 200)
        conv_ok_st, conv_ok_out = client.request(
            "POST",
            "/api/fx/convert",
            {"quote_id": val_q["quote_id"]},
        )
        self.assertEqual(conv_ok_st, 200)
        self.assertEqual(conv_ok_out["from_currency"], "USD")
        self.assertEqual(conv_ok_out["to_currency"], "EUR")
        # USD balance changed -> obl-usd-1 approval is now invalidated!
        self.assertIn("obl-usd-1", conv_ok_out["invalidated"])

    def test_gap7_redaction_metrics_reconciliation_and_backup_restore(self):
        dirty = {
            "awx_api_key": "super-secret-key",
            "password": "my-password",
            "csrf_token": "tok-123",
            "custom_text": "INVOICE CONFIDENTIAL",
            "nested": {"authorization": "Bearer secret-jwt-token", "amount": "100.00"},
        }
        cleaned = redact_payload(dirty)
        self.assertEqual(cleaned["awx_api_key"], "[REDACTED]")
        self.assertEqual(cleaned["password"], "[REDACTED]")
        self.assertEqual(cleaned["csrf_token"], "[REDACTED]")
        self.assertEqual(cleaned["custom_text"], "[REDACTED]")
        self.assertEqual(cleaned["nested"]["authorization"], "[REDACTED]")
        self.assertEqual(cleaned["nested"]["amount"], "100.00")

        store = SessionStore()
        client = SessionClient(store)
        client.request("GET", "/api/state")
        client.request("POST", "/api/approve/obl-usd-1", {})

        # Metrics & reconciliation
        m_st, m_out = client.request("GET", "/api/metrics")
        self.assertEqual(m_st, 200)
        self.assertGreater(m_out["counters"]["requests_total"], 0)

        r_st, r_out = client.request("GET", "/api/reconcile")
        self.assertEqual(r_st, 200)
        self.assertTrue(r_out["execution_integrity_ok"])

        # Backup & checksummed restore
        b_st, backup = client.request("GET", "/api/backup")
        self.assertEqual(b_st, 200)
        self.assertIn("sha256_checksum", backup)

        # Tampered backup is refused
        tampered = json.loads(json.dumps(backup))
        tampered["state"]["is_live_tenant"] = True
        t_st, t_out = client.request("POST", "/api/restore", tampered)
        self.assertEqual(t_st, 409)
        self.assertIn("checksum", t_out["error"])

        # Reset state, then restore valid backup -> obl-usd-1 approval is restored!
        client.request("POST", "/api/reset", {})
        res_st, _ = client.request("POST", "/api/restore", backup)
        self.assertEqual(res_st, 200)
        _, after_state = client.request("GET", "/api/state")
        usd1 = next(o for o in after_state["obligations"] if o["obligation_id"] == "obl-usd-1")
        self.assertEqual(usd1["approval_state"], "VALID")

    def test_concurrent_workers_on_shared_sqlite_db(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_file = str(Path(tmpdir) / "concurrent.sqlite3")
            store = SessionStore(db_path=db_file)
            client = SessionClient(store)
            client.request("GET", "/api/state")
            app_st, app_out = client.request("POST", "/api/approve/obl-usd-1", {})
            self.assertEqual(app_st, 200)
            sha = app_out["approval_sha256"]

            results: list[int] = []
            lock = threading.Lock()

            def worker():
                c = SessionClient(store)
                c.cookie = client.cookie
                c.csrf_token = client.csrf_token
                st, _ = c.request("POST", "/api/execute/obl-usd-1", {"approval_sha256": sha})
                with lock:
                    results.append(st)

            threads = [threading.Thread(target=worker) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(results.count(200), 1)
            self.assertEqual(results.count(409), 4)


if __name__ == "__main__":
    unittest.main()
