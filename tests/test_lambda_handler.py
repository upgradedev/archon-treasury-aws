"""Lambda Function URL events through the packaged handler, no AWS needed."""

import json
import unittest

from archon_demo.lambda_handler import handler


class Client:
    """Carries the session cookie like a browser would."""

    def __init__(self):
        self.cookie = None

    def call(self, method, path, body=None):
        event = {
            "requestContext": {"http": {"method": method, "path": path}},
            "headers": {"cookie": self.cookie} if self.cookie else {},
            "body": json.dumps(body) if body is not None else "",
            "isBase64Encoded": False,
        }
        out = handler(event)
        for raw in out.get("cookies", []):
            self.cookie = raw.split(";", 1)[0]
        return out


class LambdaHandlerTest(unittest.TestCase):
    def test_page_and_health(self):
        client = Client()
        page = client.call("GET", "/")
        self.assertEqual(page["statusCode"], 200)
        self.assertIn("Archon Treasury", page["body"])
        self.assertIsNotNone(client.cookie)  # session minted with the page
        health = client.call("GET", "/healthz")
        self.assertEqual(json.loads(health["body"])["status"], "ok")
        self.assertEqual(client.call("HEAD", "/")["statusCode"], 200)
        self.assertEqual(client.call("GET", "/favicon.ico")["statusCode"], 204)

    def test_story_and_stale_refusal(self):
        client = Client()
        client.call("GET", "/")
        client.call("POST", "/api/reset", {})
        self.assertEqual(client.call("POST", "/api/approve/obl-usd-1", {})["statusCode"], 200)
        self.assertEqual(client.call("POST", "/api/approve/obl-eur-1", {})["statusCode"], 200)
        dep = client.call("POST", "/api/simulate-deposit", {"currency": "EUR", "amount": "500.00"})
        self.assertEqual(json.loads(dep["body"])["invalidated"], ["obl-eur-1"])
        self.assertEqual(client.call("POST", "/api/execute/obl-usd-1", {})["statusCode"], 200)
        stale = client.call("POST", "/api/execute/obl-eur-1", {})
        self.assertEqual(stale["statusCode"], 409)

    def test_sessions_are_isolated(self):
        alice, bob = Client(), Client()
        alice.call("GET", "/")
        bob.call("GET", "/")
        alice.call("POST", "/api/approve/obl-usd-1", {})
        alice.call("POST", "/api/execute/obl-usd-1", {})
        bob_state = json.loads(bob.call("GET", "/api/state")["body"])
        self.assertEqual(bob_state["transfer_count"], 0)
        row = next(r for r in bob_state["obligations"] if r["obligation_id"] == "obl-usd-1")
        self.assertEqual(row["approval_state"], "NOT_APPROVED")

    def test_hostile_json_and_oversized_body_on_lambda(self):
        client = Client()
        client.call("GET", "/")
        self.assertEqual(client.call("POST", "/api/simulate-deposit", [])["statusCode"], 400)
        missing = client.call("POST", "/api/simulate-deposit", {})
        self.assertEqual(missing["statusCode"], 400)
        self.assertIn("currency and amount are required", json.loads(missing["body"])["error"])
        self.assertEqual(
            client.call("POST", "/api/simulate-deposit", {"currency": "EUR", "amount": "-500.00"})["statusCode"],
            409,
        )
        self.assertEqual(
            client.call("POST", "/api/simulate-deposit", {"currency": "EUR", "amount": "0.00"})["statusCode"],
            409,
        )
        oversized = client.call("POST", "/api/simulate-deposit", {"pad": "x" * 17000})
        self.assertEqual(oversized["statusCode"], 413)

    def test_metal_and_optimistic_concurrency_endpoints(self):
        client = Client()
        client.call("GET", "/")
        client.call("POST", "/api/reset", {})
        app = json.loads(client.call("POST", "/api/approve/obl-usd-1", {})["body"])
        bad_sha = client.call("POST", "/api/execute/obl-usd-1", {"approval_sha256": "0" * 64})
        self.assertEqual(bad_sha["statusCode"], 409)
        good_sha = client.call("POST", "/api/execute/obl-usd-1", {"approval_sha256": app["approval_sha256"]})
        self.assertEqual(good_sha["statusCode"], 200)
        m_call = client.call("POST", "/api/metal-call/agent-fx", {})
        self.assertEqual(m_call["statusCode"], 200)
        self.assertEqual(json.loads(m_call["body"])["calls_used"], 1)
        m_reb = client.call("POST", "/api/metal-rebalance", {"agent_id": "agent-fx", "new_price": "0.50"})
        self.assertEqual(m_reb["statusCode"], 200)
        self.assertEqual(json.loads(m_reb["body"])["changes"][0]["new_call_cap"], 100)
        self.assertEqual(client.call("POST", "/api/metal-rebalance", {})["statusCode"], 400)


if __name__ == "__main__":
    unittest.main()
