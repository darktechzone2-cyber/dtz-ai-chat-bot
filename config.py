"""DTZ AI Chat Bot — configuration.

Everything comes from environment variables (or a .env file next to main.py).
Only TELEGRAM_BOT_TOKEN is required; the rest have safe defaults.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _env(name, default=""):
    value = os.environ.get(name, default)
    return value.strip() if isinstance(value, str) else value


def _env_int_list(name):
    raw = _env(name, "")
    ids = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            ids.append(int(part))
    return ids


# --- Required: get it from @BotFather on Telegram ---------------------------
BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")

# --- Admins: your Telegram user id(s), comma separated -----------------------
ADMIN_IDS = _env_int_list("ADMIN_IDS")

# --- DTZ AI API (https://dark-tech-zone-ai.vercel.app) ------------------------
# The default key below is the PUBLIC demo key Ali's own DTZ AI web page
# already uses. Bot owners who run their own DTZ AI instance should set
# their own key here instead.
API_BASE = _env("DTZ_API_BASE", "https://dark-tech-zone-ai.vercel.app")
API_KEY = _env("DTZ_API_KEY", "DarkTech")

# --- Behaviour ----------------------------------------------------------------
DB_PATH = _env("DB_PATH", "bot.db")
HISTORY_EXCHANGES = int(_env("HISTORY_EXCHANGES", "8"))  # remembered turns/user
COOLDOWN_SECONDS = float(_env("COOLDOWN_SECONDS", "3"))
MAX_INPUT_CHARS = int(_env("MAX_INPUT_CHARS", "4000"))
HTTP_TIMEOUT = float(_env("HTTP_TIMEOUT", "120"))

# Telegram caps a message at 4096 chars; we split below that.
TG_LIMIT = 4000
