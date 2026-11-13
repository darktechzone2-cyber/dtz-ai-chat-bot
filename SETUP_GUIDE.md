# DTZ AI Chat Bot — Setup Guide

## 1. Get a Telegram bot token (2 minutes)

1. Open Telegram, search **@BotFather**, send `/newbot`.
2. Give it a name (e.g. `Dark Tech Zone AI`) and a username ending in `bot`
   (e.g. `DTZ_AI_Bot`).
3. BotFather replies with a token like `123456789:AAE...` — copy it.
4. Get your own Telegram user id for admin commands: message **@userinfobot**,
   it replies with your id number.

## 2. Install

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```
TELEGRAM_BOT_TOKEN=123456789:AAE...     # the token from @BotFather
ADMIN_IDS=7544628719                   # your Telegram user id
```

The DTZ AI lines already have working defaults — leave them alone unless you
run your own DTZ AI instance.

## 3. Run

```bash
python main.py
```

You should see `DTZ AI API online` in the log. Open your bot in Telegram and
send `/start`.

## 4. Keep it running (VPS / server)

```bash
nohup python main.py > bot.log 2>&1 &
```

Or use systemd / pm2 / a process manager of your choice. The bot stores
everything in `bot.db` (SQLite, created automatically) — back that file up
if you care about user history.

## 5. Commands for your users

| Command | What it does |
|---|---|
| any message | AI chat with memory |
| /ask \<q\> | quick one-shot answer |
| /summarize | summarize a replied-to message (add `long` for detail) |
| /reply \<msg\> | write a reply — add `roman` / `urdu` |
| /caption \<topic\> [platform] | 5 captions with hashtags |
| /new | forget this chat |
| /help | all commands |

Admin only: `/stats`, `/broadcast <message>`.

## Troubleshooting

- **"TELEGRAM_BOT_TOKEN is missing"** — you forgot step 2; copy
  `.env.example` to `.env` and paste the token.
- **"The token was rejected by the server"** — the token is wrong or the bot
  was deleted; get a fresh one from @BotFather.
- **"Sorry, the AI service did not answer"** — the DTZ AI API is down or
  unreachable from your host; check `/stats` (it shows API online/offline).
- **Bot replies slowly** — the answer streams live; first words usually
  appear in 1–3 seconds. Slow hosts / slow networks delay it.
- **Behind a proxy** — the bot honours the standard `HTTPS_PROXY` /
  `HTTP_PROXY` environment variables.

## Option B — Vercel webhook (recommended, free, no server)

Use this if you do not have a 24/7 server. Telegram wakes the bot on Vercel
for each message; nothing runs between messages.

1. Push this folder to a GitHub repo (public or private).
2. vercel.com > Add New > Project > Import the repo. Framework: leave as-is.
3. Settings > Environment Variables > add `TELEGRAM_BOT_TOKEN` = your token
   from @BotFather. (Optional: `ADMIN_IDS` = your Telegram user id.)
4. Deploy, then open `https://<project>.vercel.app/api/setup` in a browser.
   It sets the Telegram webhook and shows the result.
5. Send your bot a message on Telegram — it should answer.

Check the deployment any time at `https://<project>.vercel.app/` (status page).
If the bot stops answering, re-open /api/setup — the webhook may have been
cleared. Note: on Vercel Hobby, chat history resets when the function
recycles, and answers longer than ~60s can get cut off.
