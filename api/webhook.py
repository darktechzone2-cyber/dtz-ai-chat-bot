"""Vercel serverless entry for the DTZ AI Chat Bot (webhook mode).

Telegram sends each update as POST /api/webhook. This handler builds the
same python-telegram-bot Application the polling bot uses (same handlers,
same DTZ AI streaming), processes ONE update, and returns.

No 24/7 server is needed: Telegram wakes this function for each message.

Notes:
- SQLite lives at /tmp/bot.db on Vercel (ephemeral: users/history reset
  when the function instance recycles). Long-term stats need a KV store.
- Vercel Hobby caps this function at 60s (vercel.json maxDuration), and
  the DTZ AI call is capped at 55s (HTTP_TIMEOUT env) so a slow answer
  fails cleanly instead of being killed mid-stream.
"""

import asyncio
import json
import os
import sys

# The bot modules live in the project root, one level up from api/.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Ephemeral SQLite on Vercel; harmless locally (a real DB_PATH overrides it).
os.environ.setdefault("DB_PATH", "/tmp/bot.db")

from http.server import BaseHTTPRequestHandler  # noqa: E402

import main  # noqa: E402
from telegram import Update  # noqa: E402


def _process_update(data):
    """Build the app, feed it one Telegram update, shut it down."""
    app = main.build_app()
    update = Update.de_json(data, app.bot)

    async def _run():
        # NOTE: initialize()/shutdown() do NOT run the post_init /
        # post_shutdown callbacks — only run_polling/run_webhook do.
        # In webhook mode we must call them ourselves, or bot_data has
        # no aiohttp session and no db (KeyError on every handler).
        await app.initialize()
        try:
            await main.post_init(app)
            await app.process_update(update)
        finally:
            await app.shutdown()
            if app.post_shutdown:
                await app.post_shutdown(app)

    asyncio.run(_run())


class handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - Vercel handler naming
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
            _process_update(data)
        except Exception as exc:  # noqa: BLE001 - never retry-loop Telegram
            sys.stderr.write(f"webhook error: {exc!r}\n")
            self._send(200, {"ok": True, "warning": "update failed"})
            return
        self._send(200, {"ok": True})

    def do_GET(self):  # noqa: N802
        self._send(200, {
            "ok": True,
            "service": "dtz-ai-chat-bot",
            "mode": "webhook",
            "usage": "POST Telegram updates here; open /api/setup once "
                     "after setting TELEGRAM_BOT_TOKEN.",
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
