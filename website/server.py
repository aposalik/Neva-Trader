"""Local Nexa-Trader website and demo-only control API.

The server exposes sanitized OKX demo-account/live-market data. Agent lifecycle
controls are fixed to demo mode; no web endpoint can enable live-account trading
or submit arbitrary commands/orders.
"""
from __future__ import annotations

import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from agent_control import ControlError, agent_status, current_rules, save_rules, start_agent, stop_agent
from data_snapshot import build_snapshot, write_static_snapshot
from live_data import build_live_snapshot

SITE_ROOT = Path(__file__).resolve().parent
MAX_BODY_BYTES = 16_384


class NexaWebsiteHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE_ROOT), **kwargs)

    def do_GET(self) -> None:  # noqa: N802 — stdlib API
        parsed = urlparse(self.path)
        route = parsed.path
        if route == "/api/snapshot":
            self._send_json(build_snapshot())
            return
        if route == "/api/live":
            query = parse_qs(parsed.query)
            bar = (query.get("bar") or ["15m"])[0]
            try:
                limit = int((query.get("limit") or ["100"])[0])
            except ValueError:
                limit = 100
            force = (query.get("force") or ["0"])[0] not in {"0", "false", "False", ""}
            self._send_json(build_live_snapshot(bar=bar, limit=limit, force=force))
            return
        if route == "/api/agent":
            self._send_json({"ok": True, "agent": agent_status(), "rules": current_rules()})
            return
        if route == "/api/health":
            status = agent_status()
            self._send_json({"ok": True, "mode": "demo-control", "agentRunning": status["running"]})
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802 — stdlib API
        route = urlparse(self.path).path
        if route not in {"/api/agent/start", "/api/agent/stop", "/api/rules"}:
            self._send_json({"ok": False, "error": "Bulunamadı."}, status=HTTPStatus.NOT_FOUND)
            return
        if self.headers.get("X-Nexa-Control") != "web-ui":
            self._send_json({"ok": False, "error": "Kontrol başlığı eksik."}, status=HTTPStatus.FORBIDDEN)
            return
        try:
            if route == "/api/agent/start":
                result = {"agent": start_agent(), "rules": current_rules()}
            elif route == "/api/agent/stop":
                result = {"agent": stop_agent(), "rules": current_rules()}
            else:
                result = {"agent": agent_status(), "rules": save_rules(self._read_json_body())}
            self._send_json({"ok": True, **result})
        except ControlError as error:
            self._send_json({"ok": False, "error": str(error)}, status=HTTPStatus.CONFLICT)
        except (json.JSONDecodeError, ValueError):
            self._send_json({"ok": False, "error": "Geçersiz JSON isteği."}, status=HTTPStatus.BAD_REQUEST)

    def _read_json_body(self) -> dict[str, object]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("invalid content length") from None
        if length < 0 or length > MAX_BODY_BYTES:
            raise ValueError("request too large")
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(payload, dict):
            raise ValueError("object required")
        return payload

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        route = urlparse(self.path).path
        script_policy = "'self' 'unsafe-inline'" if route.startswith("/assets/signal-fusion") and route.endswith(".html") else "'self'"
        self.send_header("Content-Security-Policy", f"default-src 'self'; script-src {script_policy}; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; frame-src 'self'; connect-src 'self'; base-uri 'self'; form-action 'self'")
        super().end_headers()

    def _send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[nexa-web] {self.address_string()} — {fmt % args}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Serve the Nexa-Trader local web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    write_static_snapshot()
    server = ThreadingHTTPServer((args.host, args.port), NexaWebsiteHandler)
    print(f"Nexa-Trader website: http://{args.host}:{args.port}")
    print("Mode: local UI + demo-only agent controls (live-account mode disabled)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
