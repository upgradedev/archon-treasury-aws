"""Stdlib HTTP server for the anonymous judge demo. Start:

    PYTHONPATH=src python -m archon_demo.server --port 8765

Routes: GET / (page), GET /healthz, GET /DEPLOYED_SHA, GET /api/state,
POST /api/approve/<id>, POST /api/execute/<id>, POST /api/simulate-deposit,
POST /api/reset. No login. State is in memory and synthetic.
"""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from archon_demo.lambda_handler import MAX_BODY_BYTES, SECURITY_HEADERS, STORE, dispatch_http


def _send(
    handler: BaseHTTPRequestHandler,
    status: int,
    body: bytes,
    content_type: str,
    set_cookie: str | None = None,
) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    for name, value in SECURITY_HEADERS.items():
        handler.send_header(name, value)
    if set_cookie:
        handler.send_header("Set-Cookie", set_cookie)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _json(handler: BaseHTTPRequestHandler, status: int, payload: dict, set_cookie: str | None = None) -> None:
    _send(handler, status, json.dumps(payload, indent=2).encode("utf-8"), "application/json; charset=utf-8", set_cookie)


class Handler(BaseHTTPRequestHandler):
    server_version = "ArchonTreasuryDemo/0.1"

    def log_message(self, *_args) -> None:  # keep demo output readable
        pass

    def _handle(self, method: str) -> None:
        raw = ""
        if method == "POST":
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > MAX_BODY_BYTES:
                _json(self, 413, {"error": "request body too large"})
                return
            try:
                raw = self.rfile.read(length).decode("utf-8") if length else ""
            except UnicodeDecodeError as exc:
                _json(self, 400, {"error": f"bad request: {exc}"})
                return
        status, body, content_type, set_cookie = dispatch_http(
            STORE,
            method,
            self.path,
            raw,
            self.headers.get("Cookie"),
            default_sha="not-deployed-local-dev",
        )
        if method == "HEAD":
            _send(self, status, b"", content_type, set_cookie)
        elif isinstance(body, str):
            _send(self, status, body.encode("utf-8"), content_type, set_cookie)
        else:
            _json(self, status, body, set_cookie)

    def do_GET(self) -> None:
        self._handle("GET")

    def do_HEAD(self) -> None:
        self._handle("HEAD")

    def do_POST(self) -> None:
        self._handle("POST")


def main() -> None:
    parser = argparse.ArgumentParser(description="Archon Treasury anonymous demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Archon Treasury demo on http://{args.host}:{args.port}/ (Ctrl+C to stop)")
    server.serve_forever()


if __name__ == "__main__":
    main()
