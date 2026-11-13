# DTZ AI Chat Bot v1.0.0

**Chat with Dark Tech Zone AI inside Telegram — a complete, sellable bot source pack.**

Your users open Telegram, send any message, and get a real AI answer from the
DTZ AI API — with memory, so they can ask follow-ups. No sign-up, no key
needed for users. The bot runs on any cheap VPS or always-on PC.

## What it does

- **Free chat with memory** — any message gets an AI answer; the bot remembers
  the last 8 exchanges per user, so follow-up questions work.
- **Live streaming answers** — the reply appears word-by-word while the AI
  is still writing (same SSE stream the DTZ AI web page uses).
- **/ask \<question\>** — one quick answer, no memory.
- **/summarize** — reply to any message to summarize it, or
  `/summarize <text>`; add `long` for a detailed summary.
- **/reply \<message\>** — writes a ready-to-send reply to a message you
  received. Add `roman` for Roman Urdu or `urdu` for Urdu script.
- **/caption \<topic\> [platform]** — 5 ready-to-post captions with hashtags
  (instagram / tiktok / facebook / x).
- **/new** — forget the chat and start fresh.
- **Admin:** /stats (users, messages, AI answers, API status) and
  /broadcast \<message\> to all users.
- **Built-in safety:** 3-second per-user cooldown, 4000-character input cap,
  long answers split under Telegram's 4096-character limit, honest errors
  when the AI service is down.

## What it does NOT do

- No model picker, no model names anywhere — the product is only
  "Dark Tech Zone AI", exactly like the DTZ AI web page.
- No fake answers: every reply is a live call to the DTZ AI API
  (POST /api/chat). If the API is down, the bot says so.

## Run it

See `SETUP_GUIDE.md`. Short version:

```bash
pip install -r requirements.txt
cp .env.example .env        # put your @BotFather token in TELEGRAM_BOT_TOKEN
python main.py
```

## Files

| File | What it is |
|---|---|
| `main.py` | The bot: handlers, streaming replies, cooldown, admin commands |
| `dtz_ai.py` | DTZ AI API client (SSE streaming) + prompt builders |
| `db.py` | SQLite storage: users, chat history, counters |
| `config.py` | Settings from environment / `.env` |
| `requirements.txt` | python-telegram-bot 22.8, aiohttp, python-dotenv |
| `.env.example` | Copy to `.env` and fill in your token |
| `tests/test_core.py` | Unit tests (no network, no token) |
| `tests/test_live.py` | Live tests against the real DTZ AI API |

## Live test results (2026-11-14, run before delivery)

Core tests: **28/28 passed** (SSE parser, prompt builders, message splitting,
SQLite history trim + stats).

Live tests against the real DTZ AI API: **6/6 passed**
- /api/health online
- Chat streams a real answer ("2 + 2 = 4.")
- Follow-up with history works ("4 + 4 is 8.")
- /summarize prompt returns a real summary
- /reply prompt returns a Roman Urdu reply
- /caption prompt returns 5/5 numbered captions

Bot start-up smoke test: **PASS** — 10 handlers registered, start-up health
check reports "DTZ AI API online", database created, missing token exits with
a clear message.

**Not yet tested live:** a real Telegram conversation — that needs a real bot
token from @BotFather (see "Mujhe ye chahiye" in the delivery message).
The Telegram connection itself was verified: with a dummy token the bot
reached api.telegram.org and was correctly rejected (401 Unauthorized).

## Webhook mode — Vercel (free, no 24/7 server)

Polling needs a server that never sleeps. Webhook mode runs on Vercel
serverless instead: Telegram wakes the function for each message.

Files: `api/webhook.py` (receives Telegram updates), `api/setup.py`
(points Telegram at the webhook), `api/index.py` (status page),
`vercel.json` (60s max duration for the webhook function).

Deploy:
1. Push this repo to GitHub, then import it in Vercel (New Project).
2. In Vercel > Project > Settings > Environment Variables, add
   `TELEGRAM_BOT_TOKEN` (from @BotFather). Redeploy.
3. Open `https://<your-project>.vercel.app/api/setup` once — it calls
   Telegram setWebhook for you. Done: send the bot a message.

Limits (Vercel Hobby): one function call per message, 60s max per call —
very long AI answers can get cut off. SQLite lives in /tmp, so users and
chat history reset when Vercel recycles the function; stats are best-effort.
