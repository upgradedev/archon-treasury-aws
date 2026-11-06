"""Live transport plumbing against a local stub API over a real socket."""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from adapters.airwallex_client import AdapterError, AirwallexClient, DuplicateRequestError
from adapters.fx_rates_client import get_fx_rates, reset_fx_cache
from adapters.live_transport import AirwallexConfig, HttpAirwallexTransport, live_credentials_present
from fixtures import clean_snapshot, obligation
from kerdon.approvals import ApprovalIntent

SEEN = []


class StubAirwallex(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _reply(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/fx-latest":
            return self._reply(200, {"date": "2026-11-06", "rates": {"USD": 1.0912, "GBP": 0.8415}})
        return self._reply(500, {"error": "failed"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        SEEN.append((self.path, dict(self.headers), json.loads(raw) if raw else None))
        if self.path == "/api/v1/authentication/login":
            if self.headers.get("x-client-id") == "cid" and self.headers.get("x-api-key") == "key":
                return self._reply(200, {"token": "stub-token"})
            return self._reply(401, {"code": "unauthorized"})
        if self.headers.get("Authorization") != "Bearer stub-token":
            return self._reply(401, {"code": "unauthorized"})
        payload = json.loads(raw)
        if payload.get("request_id") == "req-dup":
            return self._reply(400, {"code": "duplicate_request_id"})
        return self._reply(200, {"id": "trn_stub_1", "status": "SENT"})


class LiveTransportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), StubAirwallex)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _client(self):
        config = AirwallexConfig(base_url=f"http://127.0.0.1:{self.port}", client_id="cid", api_key="key")
        return AirwallexClient(HttpAirwallexTransport(config))

    def test_missing_credentials_fail_closed(self):
        with self.assertRaises(AdapterError):
            AirwallexConfig.from_env({})
        with self.assertRaises(AdapterError):
            AirwallexConfig.from_env({"AWX_CLIENT_ID": "cid"})

    def test_auth_then_transfer_over_socket(self):
        SEEN.clear()
        intent = ApprovalIntent.from_snapshot(clean_snapshot(), obligation(), "net-14")
        transfer_id = self._client().execute(intent, "req-live-1")
        self.assertEqual(transfer_id, "trn_stub_1")
        paths = [row[0] for row in SEEN]
        self.assertEqual(paths, ["/api/v1/authentication/login", "/api/v1/transfers/create"])
        transfer_payload = SEEN[1][2]
        self.assertEqual(transfer_payload["amount"], "50.00")  # Trap T2 at the wire

    def test_duplicate_request_id_maps_to_domain_error(self):
        intent = ApprovalIntent.from_snapshot(clean_snapshot(), obligation(), "net-14")
        with self.assertRaises(DuplicateRequestError):
            self._client().execute(intent, "req-dup")

    def test_live_credentials_present(self):
        self.assertFalse(live_credentials_present({}))
        self.assertFalse(live_credentials_present({"AWX_CLIENT_ID": "cid"}))
        self.assertTrue(live_credentials_present({"AWX_CLIENT_ID": "cid", "AWX_API_KEY": "key"}))

    def test_get_fx_rates_and_cache(self):
        reset_fx_cache()
        offline = get_fx_rates(allow_network=False)
        self.assertEqual(offline["source"], "ecb-reference-rates-pinned-offline")
        self.assertEqual(offline["eur_usd"], "1.0845")

        # Network error falls back cleanly
        failed = get_fx_rates(allow_network=True, endpoint=f"http://127.0.0.1:{self.port}/fx-broken")
        self.assertEqual(failed["source"], "ecb-reference-rates-pinned-offline")

        # Live HTTP fetch succeeds and caches
        live = get_fx_rates(allow_network=True, endpoint=f"http://127.0.0.1:{self.port}/fx-latest")
        self.assertEqual(live["source"], "ecb-reference-rates-live")
        self.assertEqual(live["eur_usd"], "1.0912")
        self.assertEqual(live["eur_gbp"], "0.8415")
        cached = get_fx_rates(allow_network=False)
        self.assertEqual(cached["eur_usd"], "1.0912")
        reset_fx_cache()


if __name__ == "__main__":
    unittest.main()
