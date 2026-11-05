"""UAT for judging: persona journeys, races, hostile input, static deploy checks."""

import http.client
import json
import threading
import time
import unittest
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

from archon_demo.page import PAGE
from archon_demo.server import Handler
from archon_demo.service import DemoService
from fixtures import clean_snapshot
from kerdon.completeness import evaluate
from kerdon.errors import DomainError

AS_OF = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


class JourneyTest(unittest.TestCase):
    def test_double_execute_is_refused_money_moves_once(self):
        service = DemoService.seeded(AS_OF)
        service.approve("obl-usd-1")
        service.execute("obl-usd-1")
        with self.assertRaises(DomainError):
            service.execute("obl-usd-1")
        self.assertEqual(service.transport.transfer_count, 1)

    def test_concurrent_execute_race_has_single_winner(self):
        service = DemoService.seeded(AS_OF)
        service.approve("obl-usd-1")
        wins, refusals = [], []

        def attempt():
            try:
                wins.append(service.execute("obl-usd-1"))
            except DomainError:
                refusals.append(1)

        threads = [threading.Thread(target=attempt) for _ in range(8)]
        [t.start() for t in threads]
        [t.join(timeout=10) for t in threads]
        self.assertEqual(len(wins), 1)
        self.assertEqual(len(refusals), 7)
        self.assertEqual(service.transport.transfer_count, 1)

    def test_reset_restores_pristine_scenario(self):
        service = DemoService.seeded(AS_OF)
        service.approve("obl-usd-1")
        service.execute("obl-usd-1")
        service.reset()
        state = service.state()
        self.assertEqual(state["transfer_count"], 0)
        self.assertTrue(all(r["approval_state"] == "NOT_APPROVED" for r in state["obligations"]))

    def test_reserve_floor_refusal_and_deposit_recovery(self):
        service = DemoService.seeded(AS_OF)
        service.approve("obl-usd-1")
        service.execute("obl-usd-1")  # USD balance is now $2,050.00; floor is $500.00
        service.approve("obl-usd-2")  # $1,650.00 would leave $400.00 < $500.00 floor
        row = next(r for r in service.state()["obligations"] if r["obligation_id"] == "obl-usd-2")
        self.assertEqual(row["approval_state"], "INVALIDATED")
        self.assertIn("reserve-floor-breach", row["action_reason"])
        with self.assertRaises(DomainError):
            service.execute("obl-usd-2")
        service.simulate_deposit("USD", "200.00")
        service.approve("obl-usd-2")
        paid = service.execute("obl-usd-2")
        self.assertEqual(paid["state"], "PAID")

    @unittest.skipIf(__import__("sys").gettrace() is not None, "timing is not a product measure under the coverage tracer")
    def test_engine_speed_budget(self):
        snap = clean_snapshot()
        start = time.perf_counter()
        for _ in range(200):
            evaluate(snap)
        self.assertLess(time.perf_counter() - start, 1.0)


class AccessibilityStaticTest(unittest.TestCase):
    def test_page_landmarks_labels_and_single_h1(self):
        self.assertEqual(PAGE.count("<h1"), 1)
        for marker in ('href="#main"', 'id="main"', 'for="currency"', 'for="amount"',
                       'aria-live="polite"', 'role="status"', "<header>", "<footer>",
                       "erp-shell", "erp-sidebar", 'id="company-select"',
                       'id="cmdk-modal"', "tabular-nums", "font-mono"):
            self.assertIn(marker, PAGE)


class HttpHardeningTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request(method, path, body=body, headers=headers or {"Content-Type": "application/json"})
        res = conn.getresponse()
        data = res.read().decode()
        result = (res.status, dict(res.getheaders()), data)
        conn.close()
        return result

    def test_security_headers_on_page_and_api(self):
        for path in ("/", "/healthz"):
            _status, headers, _body = self._request("GET", path)
            self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
            self.assertIn("frame-ancestors 'none'", headers.get("Content-Security-Policy", ""))

    def test_bad_json_is_400_not_500(self):
        status, _headers, _body = self._request("POST", "/api/simulate-deposit", body="{not json")
        self.assertEqual(status, 400)
        status, _headers, body = self._request("POST", "/api/simulate-deposit", body="[]")
        self.assertEqual(status, 400)
        self.assertIn("JSON object", json.loads(body)["error"])
        status, _headers, body = self._request("POST", "/api/simulate-deposit", body="{}")
        self.assertEqual(status, 400)
        self.assertIn("currency and amount are required", json.loads(body)["error"])
        status, _headers, _body = self._request(
            "POST", "/api/simulate-deposit", body='{"currency":"EUR","amount":"-500.00"}'
        )
        self.assertEqual(status, 409)
        for head_path in ("/", "/healthz", "/DEPLOYED_SHA", "/api/state"):
            self.assertEqual(self._request("HEAD", head_path)[0], 200)
        self.assertEqual(self._request("HEAD", "/favicon.ico")[0], 204)

    def test_oversized_body_is_413(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.putrequest("POST", "/api/simulate-deposit")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", "99999")
        conn.endheaders(b"{}")
        res = conn.getresponse()
        res.read()
        conn.close()
        self.assertEqual(res.status, 413)

    def test_unknown_obligation_is_409_with_reason(self):
        status, _headers, body = self._request("POST", "/api/approve/obl-nope", body="{}")
        self.assertEqual(status, 409)
        self.assertIn("unknown obligation", json.loads(body)["error"])


class DeployArtifactsStaticTest(unittest.TestCase):
    def test_dockerfile_terraform_ci_contracts(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("archon_demo.server", dockerfile)
        self.assertNotIn("AWX_API_KEY", dockerfile)
        tf = (ROOT / "infra" / "main.tf").read_text(encoding="utf-8")
        self.assertIn("DEPLOYED_SHA", tf)
        self.assertIn("lambda:InvokeFunctionUrl", tf)
        self.assertIn("invoked_via_function_url = true", tf)  # Trap T5 regression guard
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("verify_gates.py --self-test", ci)


if __name__ == "__main__":
    unittest.main()
