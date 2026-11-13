"""DTZ AI Chat Bot v1.0.0 — Telegram bot powered by the DTZ AI API.

Chat with Dark Tech Zone AI inside Telegram: free chat with memory,
/ask, /summarize, /reply and /caption commands, plus admin /stats
and /broadcast. No sign-up, no key needed for users — the bot talks to
the DTZ AI API (https://dark-tech-zone-ai.vercel.app).

Run:  pip install -r requirements.txt
      cp .env.example .env   # put your @BotFather token in it
      python main.py
"""

import asyncio
import logging
import time

import aiohttp
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
import db as store
from dtz_ai import (
    build_caption_prompt,
    build_chat_question,
    build_reply_prompt,
    build_summary_prompt,
    check_health,
    split_message,
    stream_chat,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
log = logging.getLogger("dtz-ai-bot")

HELP_TEXT = (
    "Dark Tech Zone AI — chat with AI right here in Telegram.\n\n"
    "Just send any message and I will answer. I remember our last "
    "few messages, so you can ask follow-ups.\n\n"
    "Commands:\n"
    "/ask <question> — one quick answer (no memory)\n"
    "/summarize — reply to any message to summarize it, "
    "or /summarize <text>; add 'long' for a detailed summary\n"
    "/reply <message> — write a ready-to-send reply; "
    "add 'roman' or 'urdu' for Roman Urdu / Urdu script\n"
    "/caption <topic> [platform] — 5 ready-to-post captions "
    "with hashtags (instagram, tiktok, facebook, x)\n"
    "/new — forget this chat and start fresh\n"
    "/help — show this help\n\n"
    "Made by Dark Tech Zone."
)

START_TEXT = (
    "Welcome to Dark Tech Zone AI.\n\n"
    "Send me any question and I will answer — I remember our "
    "conversation, so ask follow-ups freely.\n\n"
    "Try: /ask What is the difference between HTTP and HTTPS?\n"
    "Or just type a message.\n\n"
    "See /help for all commands."
)

_last_call = {}  # user_id -> timestamp of last AI request


def _cooldown_left(user_id):
    now = time.monotonic()
    last = _last_call.get(user_id, 0)
    left = config.COOLDOWN_SECONDS - (now - last)
    return max(0.0, left)


def _touch(user_id):
    _last_call[user_id] = time.monotonic()


def _is_admin(user_id):
    return user_id in config.ADMIN_IDS





async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = context.application.bot_data["db"]
    user = update.effective_user
    store.record_user(conn, user.id, user.username, user.first_name)
    await update.message.reply_text(START_TEXT)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)


async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = context.application.bot_data["db"]
    store.clear_history(conn, update.effective_user.id)
    await update.message.reply_text(
        "Done — I forgot our previous chat. Send a new message to start fresh."
    )


async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = " ".join(context.args).strip()
    if not question:
        await update.message.reply_text(
            "Usage: /ask <your question>\nExample: /ask What is 5G?"
        )
        return
    await _run_ai(update, context, question, remember=False)


async def summarize_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, detailed = "", False
    if update.message.reply_to_message and update.message.reply_to_message.text:
        text = update.message.reply_to_message.text
        detailed = any(a.lower() == "long" for a in context.args)
    else:
        args = [a for a in context.args if a.lower() != "long"]
        detailed = len(args) != len(context.args)
        text = " ".join(args).strip()
    if not text:
        await update.message.reply_text(
            "Reply to a message with /summarize, or use "
            "/summarize <text>. Add 'long' for a detailed summary."
        )
        return
    if len(text) > config.MAX_INPUT_CHARS:
        text = text[: config.MAX_INPUT_CHARS]
    await _run_ai(
        update, context, build_summary_prompt(text, detailed), remember=False,
        thinking="Summarizing...",
    )


async def reply_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = "english"
    args = []
    for arg in context.args:
        low = arg.lower()
        if low in ("roman", "urdu"):
            language = low
        else:
            args.append(arg)
    text = " ".join(args).strip()
    if not text:
        await update.message.reply_text(
            "Usage: /reply <the message you got>\n"
            "Add 'roman' for a Roman Urdu reply or 'urdu' for Urdu script.\n"
            "Example: /reply roman kal milte hain?"
        )
        return
    if len(text) > config.MAX_INPUT_CHARS:
        text = text[: config.MAX_INPUT_CHARS]
    await _run_ai(
        update, context, build_reply_prompt(text, language), remember=False,
        thinking="Writing your reply...",
    )


async def caption_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    platforms = ("instagram", "tiktok", "facebook", "x", "twitter")
    platform, topic_parts = "instagram", []
    for arg in context.args:
        if arg.lower() in platforms:
            platform = "x" if arg.lower() == "twitter" else arg.lower()
        else:
            topic_parts.append(arg)
    topic = " ".join(topic_parts).strip()
    if not topic:
        await update.message.reply_text(
            "Usage: /caption <topic> [platform]\n"
            "Example: /caption chai time tiktok"
        )
        return
    await _run_ai(
        update, context, build_caption_prompt(topic, platform), remember=False,
        thinking="Writing captions...",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Free chat: remember the conversation and answer with context."""
    user = update.effective_user
    text = (update.message.text or "").strip()
    if not text:
        return
    if len(text) > config.MAX_INPUT_CHARS:
        await update.message.reply_text(
            f"That message is too long — please keep it under "
            f"{config.MAX_INPUT_CHARS} characters."
        )
        return
    conn = context.application.bot_data["db"]
    store.record_user(conn, user.id, user.username, user.first_name)
    history = store.get_history(conn, user.id, config.HISTORY_EXCHANGES)
    question = build_chat_question(history, text)
    answer = await _run_ai(update, context, question, remember=False)
    if answer:
        store.add_exchange(
            conn, user.id, text, answer, config.HISTORY_EXCHANGES
        )


async def _run_ai(update, context, question, remember, thinking="Thinking..."):
    """Shared path for every AI command: cooldown, typing, stream, errors."""
    user = update.effective_user
    left = _cooldown_left(user.id)
    if left > 0:
        await update.message.reply_text(
            f"Please wait {left:.0f} more second(s) before the next question."
        )
        return ""
    _touch(user.id)
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        return await _send_streaming_with_label(
            update, context, question, thinking
        )
    except Exception as exc:  # noqa: BLE001 - surface any API/network failure
        log.exception("AI request failed")
        await update.message.reply_text(
            "Sorry, the AI service did not answer right now. "
            "Please try again in a minute."
        )
        return ""


async def _send_streaming_with_label(update, context, question, label):
    session = context.application.bot_data["session"]
    sent = await update.message.reply_text(label)
    full = ""
    last_edit = 0.0

    async def on_chunk(text):
        nonlocal full, last_edit
        full = text
        now = time.monotonic()
        if now - last_edit < 1.0 or len(text) < 10:
            return
        last_edit = now
        try:
            await sent.edit_text(text[: config.TG_LIMIT])
        except Exception:
            pass

    answer = await stream_chat(
        session, config.API_BASE, config.API_KEY, question,
        on_chunk=on_chunk, timeout=config.HTTP_TIMEOUT,
    )
    conn = context.application.bot_data["db"]
    store.bump_counter(conn, "ai_calls")
    if not answer:
        await sent.edit_text(
            "Sorry, I got an empty answer. Please try again."
        )
        return ""
    parts = split_message(answer)
    await sent.edit_text(parts[0])
    for extra in parts[1:]:
        await update.message.reply_text(extra)
    return answer


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("This command is for the bot admin.")
        return
    conn = context.application.bot_data["db"]
    stats = store.get_stats(conn)
    online = await check_health(
        context.application.bot_data["session"], config.API_BASE
    )
    await update.message.reply_text(
        "DTZ AI Chat Bot — stats\n\n"
        f"Users: {stats['users']}\n"
        f"Messages: {stats['messages']}\n"
        f"AI answers: {stats['ai_calls']}\n"
        f"DTZ AI API: {'online' if online else 'offline'}"
    )


async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("This command is for the bot admin.")
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    conn = context.application.bot_data["db"]
    user_ids = [
        r["user_id"]
        for r in conn.execute("SELECT user_id FROM users").fetchall()
    ]
    sent, failed = 0, 0
    for user_id in user_ids:
        try:
            await context.bot.send_message(user_id, text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await update.message.reply_text(
        f"Broadcast done: {sent} delivered, {failed} failed."
    )


async def on_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Update failed: %s", context.error)


async def post_init(application: Application):
    application.bot_data["session"] = aiohttp.ClientSession(trust_env=True)
    application.bot_data["db"] = store.connect(config.DB_PATH)
    online = await check_health(application.bot_data["session"], config.API_BASE)
    log.info("DTZ AI API %s", "online" if online else "OFFLINE — check API_BASE")


async def post_shutdown(application: Application):
    await application.bot_data["session"].close()


def build_app():
    """Build the bot application (handlers registered, not yet polling)."""
    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("new", new_chat))
    app.add_handler(CommandHandler("ask", ask_cmd))
    app.add_handler(CommandHandler("summarize", summarize_cmd))
    app.add_handler(CommandHandler("reply", reply_cmd))
    app.add_handler(CommandHandler("caption", caption_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    app.add_error_handler(on_error)
    return app


def main():
    if not config.BOT_TOKEN:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN is missing. Copy .env.example to .env and "
            "put the token from @BotFather in it."
        )
    app = build_app()
    log.info("DTZ AI Chat Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
