"""GET / — tiny status page for the webhook deployment."""

import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler


def _api_online():
    base = os.environ.get(
        "DTZ_API_BASE", "https://dark-tech-zone-ai.vercel.app"
    ).rstrip("/")
    try:
        with urllib.request.urlopen(base + "/api/health", timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8")).get("status") == "online"
    except Exception:
        return False


class handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self._send(200, {
            "ok": True,
            "service": "DTZ AI Chat Bot",
            "mode": "webhook (Vercel serverless)",
            "token_set": bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
            "dtz_ai_api": "online" if _api_online() else "offline",
            "webhook": "/api/webhook",
            "setup": "/api/setup (open once after setting TELEGRAM_BOT_TOKEN)",
        })

    def _send(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
