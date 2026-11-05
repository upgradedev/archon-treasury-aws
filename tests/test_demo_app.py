"""Demo story at service level and over real HTTP on an ephemeral port."""

import http.cookiejar
import json
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer

from archon_demo.server import Handler
from archon_demo.service import DemoService
from kerdon.errors import DomainError

AS_OF = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)


class ServiceStoryTest(unittest.TestCase):
    def test_seed_has_five_obligations_three_currencies(self):
        service = DemoService.seeded(AS_OF)
        state = service.state()
        self.assertEqual(len(state["obligations"]), 5)
        self.assertEqual(len(state["balances"]), 3)
        self.assertEqual(state["mode"], "synthetic-demo-fake-transport")

    def test_hero_story_only_affected_falls_valid_executes(self):
        service = DemoService.seeded(AS_OF)
        service.approve("obl-usd-1")
        service.approve("obl-eur-1")
        outcome = service.simulate_deposit("EUR", "500.00")
        self.assertEqual(outcome["invalidated"], ["obl-eur-1"])
        self.assertEqual(outcome["still_valid"], ["obl-usd-1"])
        rules_after_deposit = {f["rule_id"] for f in service.state()["findings"]}
        self.assertIn("R18", rules_after_deposit)  # stale pending approval surfaces in findings
        paid = service.execute("obl-usd-1")
        self.assertEqual(paid["state"], "PAID")
        self.assertEqual(service.transport.transfer_count, 1)
        with self.assertRaises(DomainError):
            service.execute("obl-eur-1")  # stale approval refuses at the gate
        self.assertEqual(service.transport.transfer_count, 1)  # still just one transfer
        service.approve("obl-eur-1")
        rules_after_reapprove = {f["rule_id"] for f in service.state()["findings"]}
        self.assertNotIn("R18", rules_after_reapprove)

    def test_optimistic_concurrency_digest_mismatch_refused(self):
        service = DemoService.seeded(AS_OF)
        approved = service.approve("obl-usd-1")
        with self.assertRaises(DomainError):
            service.execute("obl-usd-1", expected_sha256="0" * 64)
        paid = service.execute("obl-usd-1", expected_sha256=approved["approval_sha256"])
        self.assertEqual(paid["state"], "PAID")

    def test_metal_usdz_governor_in_demo_service(self):
        service = DemoService.seeded(AS_OF)
        agents = {a["agent_id"]: a for a in service.state()["metal_agents"]}
        self.assertEqual(agents["agent-fx"]["call_cap"], 200)
        call_res = service.pay_metal_call("agent-fx")
        self.assertEqual(call_res["calls_used"], 1)
        reb = service.rebalance_metal("agent-fx", "0.50")
        self.assertEqual(reb["changes"][0]["new_call_cap"], 100)
        agents_after = {a["agent_id"]: a for a in service.state()["metal_agents"]}
        self.assertEqual(agents_after["agent-fx"]["call_cap"], 100)
        self.assertEqual(agents_after["agent-docs"]["call_cap"], 300)

    def test_receipt_is_spoken_and_sealed(self):
        service = DemoService.seeded(AS_OF)
        service.approve("obl-usd-1")
        row = next(r for r in service.state()["obligations"] if r["obligation_id"] == "obl-usd-1")
        self.assertTrue(row["receipt"]["merkle_verified"])
        self.assertIn("USD 450.00 (45000 cents)", row["receipt"]["spoken_text"])

    def test_blocked_action_carries_visible_reason(self):
        service = DemoService.seeded(AS_OF)
        row = service.state()["obligations"][0]
        self.assertEqual(row["approval_state"], "NOT_APPROVED")
        self.assertTrue(row["action_reason"])  # H2: never a bare disabled control


class HttpStoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _call(self, path, body=None):
        opener = getattr(self, "_opener", None)
        if opener is None:
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
            )
            self._opener = opener
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with opener.open(req, timeout=5) as res:
                return res.status, res.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()

    def test_page_is_anonymous_and_accessible_shaped(self):
        status, html = self._call("/")
        self.assertEqual(status, 200)
        for marker in ('lang="en"', "<header>", "<main", 'aria-live="polite"', "reserve floor"):
            self.assertIn(marker, html)

    def test_health_and_state(self):
        self._call("/api/reset", {})
        status, body = self._call("/healthz")
        self.assertEqual((status, json.loads(body)["status"]), (200, "ok"))
        status, body = self._call("/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["obligations"]), 5)

    def test_full_story_over_http(self):
        self._call("/api/reset", {})
        self.assertEqual(self._call("/api/approve/obl-usd-1", {})[0], 200)
        self.assertEqual(self._call("/api/approve/obl-eur-1", {})[0], 200)
        status, body = self._call("/api/simulate-deposit", {"currency": "EUR", "amount": "500.00"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["invalidated"], ["obl-eur-1"])
        self.assertEqual(self._call("/api/execute/obl-usd-1", {})[0], 200)
        status, body = self._call("/api/execute/obl-eur-1", {})
        self.assertEqual(status, 409)
        self.assertIn("stale", json.loads(body)["error"])


if __name__ == "__main__":
    unittest.main()
