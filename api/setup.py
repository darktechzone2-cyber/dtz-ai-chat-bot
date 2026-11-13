"""GET /api/setup — point Telegram at this deployment's webhook.

Reads TELEGRAM_BOT_TOKEN from the environment, builds the webhook URL
from this request's own Host header, and calls Telegram setWebhook.
The token never leaves the server: it is only read from env.
"""

import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler


def _webhook_url(host):
    return f"https://{host.strip()}/api/webhook"


def _set_webhook(token, webhook_url):
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/setWebhook",
        data=json.dumps({
            "url": webhook_url,
            "allowed_updates": ["message", "edited_message", "callback_query"],
            "drop_pending_updates": False,
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


class handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
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
        webhook_url = _webhook_url(host)
        try:
            result = _set_webhook(token, webhook_url)
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

    def log_message(self, *args):
        pass
