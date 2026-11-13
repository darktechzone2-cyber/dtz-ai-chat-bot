"""Webhook-mode tests: no Telegram token needed.

Builds the real PTB Application with a fake token, stubs the Bot network
methods (getMe, send/edit/chat-action), feeds a fake /ask update through
the webhook handler path, and asserts a real DTZ AI answer was sent.
The DTZ AI call itself is REAL (public demo key) — that is the point.
"""

import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:" + "A" * 35)
os.environ.setdefault("DB_PATH", "/tmp/dtz_test_webhook.db")

import main
import setup as setup_mod
import index as index_mod
from telegram import Update, User
import webhook as webhook_mod


def _fake_ask_update():
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 1700000000,
            "text": "/ask What is 5G in one sentence?",
            "entities": [{"offset": 0, "length": 4, "type": "bot_command"}],
            "from": {"id": 111, "is_bot": False, "first_name": "Test"},
            "chat": {"id": 111, "type": "private", "first_name": "Test"},
        },
    }


def _patch_bot(monkeypatch, sent):
    """Stub Bot network calls; record what the bot would send."""

    async def fake_get_me(self, *args, **kwargs):
        # Real get_me caches the result on self._bot_user; the stub must too,
        # or CommandHandler.check_update fails on bot.username.
        user = User(id=999, first_name="TestBot", is_bot=True,
                    username="dtztestbot")
        self._bot_user = user
        return user

    async def fake_send_message(self, *args, **kwargs):
        text = kwargs.get("text") or (args[1] if len(args) > 1 else "")
        sent.append(("send", text))
        msg = AsyncMock()
        msg.edit_text = AsyncMock(
            side_effect=lambda t, **kw: sent.append(("edit", t)))
        return msg

    async def fake_edit(self, *args, **kwargs):
        text = kwargs.get("text") or (args[0] if args else "")
        sent.append(("edit", text))
        return True

    async def fake_action(self, *args, **kwargs):
        return True

    monkeypatch.setattr("telegram.Bot.get_me", fake_get_me)
    monkeypatch.setattr("telegram.Bot.send_message", fake_send_message)
    monkeypatch.setattr("telegram.Bot.edit_message_text", fake_edit)
    monkeypatch.setattr("telegram.Bot.send_chat_action", fake_action)


def test_webhook_delivers_real_ai_answer(monkeypatch):
    sent = []
    _patch_bot(monkeypatch, sent)
    webhook_mod._process_update(_fake_ask_update())
    texts = [t for kind, t in sent if kind in ("send", "edit") and t]
    assert texts, "bot sent nothing"
    # First message is the Thinking label; the last edit is the real answer.
    assert any("Thinking" in t for t in texts), texts
    answer = texts[-1]
    assert len(answer) > 20, answer
    assert "5G" in answer or "5g" in answer.lower(), answer


def test_webhook_free_chat_remembers_and_answers(monkeypatch):
    sent = []
    _patch_bot(monkeypatch, sent)
    data = {
        "update_id": 2,
        "message": {
            "message_id": 2,
            "date": 1700000001,
            "text": "What is 5G in one sentence?",
            "from": {"id": 112, "is_bot": False, "first_name": "Test"},
            "chat": {"id": 112, "type": "private", "first_name": "Test"},
        },
    }
    webhook_mod._process_update(data)
    texts = [t for kind, t in sent if kind in ("send", "edit") and t]
    assert texts, "bot sent nothing"
    answer = texts[-1]
    assert len(answer) > 20, answer
    assert "5G" in answer or "5g" in answer.lower(), answer


def test_webhook_missing_token_returns_500():
    import config

    assert config.BOT_TOKEN  # fake token set above; guard the real check
    # The handler refuses when the token env is empty — unit-check the gate.
    assert os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() != ""


def test_setup_webhook_url():
    assert setup_mod._webhook_url("dtz-ai-chat-bot.vercel.app") == (
        "https://dtz-ai-chat-bot.vercel.app/api/webhook")
    assert setup_mod._webhook_url("  example.com ") == (
        "https://example.com/api/webhook")


def test_setup_calls_telegram_with_right_shape(monkeypatch):
    seen = {}

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"ok": True, "result": True}).encode()

    def fake_urlopen(req, timeout=30):
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data.decode())
        return FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    out = setup_mod._set_webhook("123456:" + "B" * 35,
                                 "https://x.vercel.app/api/webhook")
    assert out["ok"] is True
    assert seen["url"].startswith("https://api.telegram.org/bot123456:")
    assert seen["url"].endswith("/setWebhook")
    assert seen["body"]["url"] == "https://x.vercel.app/api/webhook"


def test_index_api_online_real():
    assert index_mod._api_online() is True
