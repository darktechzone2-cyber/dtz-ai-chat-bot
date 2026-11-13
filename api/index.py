"""Single dispatcher for the DTZ AI Chat Bot on Vercel.

This deployment's routing sends every path to api/index.py, so this file
dispatches by request path instead of relying on one-function-per-file
routing. api/webhook.py and api/setup.py still exist as standalone
functions too (they work if the runtime routes to them directly).

Routes:
  GET  /              -> status JSON
  GET  /api/index     -> status JSON
  GET  /api/webhook   -> webhook info JSON
  POST /api/webhook   -> process one Telegram update (the real bot path)
  GET  /api/setup     -> set the Telegram webhook to this deployment
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(__file__))          # api/ modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # root modules

os.environ.setdefault("DB_PATH", "/tmp/bot.db")

import setup as setup_mod  # noqa: E402
import webhook as webhook_mod  # noqa: E402


def _api_online():
    """True when the real DTZ AI API answers /api/health with online."""
    import urllib.request

    base = os.environ.get(
        "DTZ_API_BASE", "https://dark-tech-zone-ai.vercel.app"
    ).rstrip("/")
    try:
        with urllib.request.urlopen(base + "/api/health", timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8")).get("status") == "online"
    except Exception:
        return False


def _status():
    online = _api_online()
    return {
        "ok": True,
        "service": "DTZ AI Chat Bot",
        "mode": "webhook (Vercel serverless)",
        "token_set": bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
        "dtz_ai_api": "online" if online else "offline",
        "webhook": "/api/webhook",
        "setup": "/api/setup (open once after setting TELEGRAM_BOT_TOKEN)",
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path in ("/", "/api/index"):
            self._send(200, _status())
        elif path == "/api/webhook":
            self._send(200, {
                "ok": True,
                "service": "dtz-ai-chat-bot",
                "mode": "webhook",
                "usage": "POST Telegram updates here; open /api/setup once "
                         "after setting TELEGRAM_BOT_TOKEN.",
            })
        elif path == "/api/setup":
            self._do_setup()
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path != "/api/webhook":
            self._send(404, {"ok": False, "error": "not found"})
            return
        import config as _config

        if not _config.BOT_TOKEN:
            self._send(500, {
                "ok": False,
                "error": "TELEGRAM_BOT_TOKEN is not set in this deployment. "
                         "Add it in Vercel > Settings > Environment Variables, "
                         "redeploy, then open /api/setup once.",
            })
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._send(400, {"ok": False, "error": "invalid JSON"})
            return
        try:
            webhook_mod._process_update(data)
        except Exception as exc:  # noqa: BLE001 - never retry-loop Telegram
            sys.stderr.write(f"webhook error: {exc!r}\n")
            self._send(200, {"ok": True, "warning": "update failed"})
            return
        self._send(200, {"ok": True})

    def _do_setup(self):
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            self._send(500, {
                "ok": False,
                "error": "TELEGRAM_BOT_TOKEN is not set in this deployment. "
                         "Add it in Vercel > Project > Settings > Environment "
                         "Variables, redeploy, then open /api/setup again.",
            })
            return
        host = (self.headers.get("Host") or "").strip()
        if not host:
            self._send(400, {"ok": False, "error": "missing Host header"})
            return
        webhook_url = setup_mod._webhook_url(host)
        try:
            result = setup_mod._set_webhook(token, webhook_url)
        except Exception as exc:  # noqa: BLE001
            self._send(502, {"ok": False, "error": f"Telegram call failed: {exc}"})
            return
        self._send(200, {
            "ok": bool(result.get("ok")),
            "webhook_url": webhook_url,
            "telegram": result,
        })

    def _send(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep Vercel logs clean
        pass
