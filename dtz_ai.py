"""Client for the DTZ AI API + the prompt builders the bot sends it.

The API is a plain HTTP endpoint:
    POST {base}/api/chat   header X-API-Key: <key>   body {"q": "..."}
    -> Server-Sent Events:  data: {"chunk": "..."} ... data: [DONE]
    GET  {base}/api/health -> {"status": "online", ...}

No model name is ever sent or shown: the product is only "Dark Tech Zone AI".
"""

import asyncio
import json

import aiohttp

IDENTITY = (
    "You are Dark Tech Zone AI, the helpful assistant of Dark Tech Zone. "
    "Answer clearly and helpfully. If asked who made you, say you were made "
    "by Dark Tech Zone."
)


def parse_sse_line(line):
    """Parse one SSE line. Returns (chunk_text_or_None, is_done_bool)."""
    line = line.strip()
    if not line.startswith("data:"):
        return None, False
    payload = line[len("data:"):].strip()
    if payload == "[DONE]":
        return None, True
    if not payload:
        return None, False
    try:
        obj = json.loads(payload)
    except json.JSONDecodeError:
        # Tolerate a plain-text chunk.
        return payload, False
    if isinstance(obj, dict):
        chunk = obj.get("chunk")
        if isinstance(chunk, str):
            return chunk, False
        text = obj.get("text") or obj.get("answer") or obj.get("content")
        if isinstance(text, str):
            return text, False
    return None, False


async def stream_chat(session, base, key, question, on_chunk=None, timeout=120):
    """Send one question, collect the streamed answer. Returns full text."""
    url = base.rstrip("/") + "/api/chat"
    headers = {"X-API-Key": key, "Content-Type": "application/json"}
    parts = []
    async with session.post(
        url, json={"q": question}, headers=headers,
        timeout=aiohttp.ClientTimeout(total=timeout),
    ) as resp:
        if resp.status != 200:
            body = await resp.text()
            raise RuntimeError(f"DTZ AI API returned HTTP {resp.status}: {body[:200]}")
        async for raw in resp.content:
            line = raw.decode("utf-8", "replace")
            for piece in line.splitlines():
                chunk, done = parse_sse_line(piece)
                if done:
                    return "".join(parts).strip()
                if chunk:
                    parts.append(chunk)
                    if on_chunk is not None:
                        await on_chunk("".join(parts))
    return "".join(parts).strip()


async def check_health(session, base, timeout=15):
    """True when the DTZ AI API answers /api/health with status online."""
    url = base.rstrip("/") + "/api/health"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            if resp.status != 200:
                return False
            data = await resp.json(content_type=None)
            return str(data.get("status", "")).lower() == "online"
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        return False


# ---------------------------------------------------------------- prompts

def build_chat_question(history, user_text):
    """history: list of (role, text) oldest-first, already trimmed by caller."""
    lines = [IDENTITY, ""]
    if history:
        lines.append("Conversation so far:")
        for role, text in history:
            lines.append(f"{'User' if role == 'user' else 'Assistant'}: {text}")
        lines.append("")
    lines.append(f"User: {user_text}")
    lines.append("Assistant:")
    return "\n".join(lines)


def build_summary_prompt(text, detailed=False):
    style = (
        "a detailed summary with the key points as short bullet lines"
        if detailed else
        "a short summary in 3-5 lines, only the main points"
    )
    return (
        f"{IDENTITY}\n\nSummarize the following text as {style}. "
        "Keep the original language of the text.\n\n"
        f"Text:\n{text}\n\nSummary:"
    )


def build_reply_prompt(text, language="english"):
    lang_line = {
        "english": "Write the reply in English.",
        "roman": "Write the reply in Roman Urdu (Urdu written with English letters).",
        "urdu": "Write the reply in Urdu script.",
    }.get(language, "Write the reply in English.")
    return (
        f"{IDENTITY}\n\nSomeone sent me this message and I need a good reply to it. "
        f"{lang_line} Keep it natural, polite and ready to send — no explanation, "
        "just the reply itself.\n\n"
        f"Message:\n{text}\n\nReply:"
    )


def build_caption_prompt(topic, platform="instagram"):
    return (
        f"{IDENTITY}\n\nWrite exactly 5 different ready-to-post captions for a "
        f"{platform} post about: {topic}\n"
        "Each caption must be on its own numbered line (1. ... 2. ... and so on), "
        "include 3-5 relevant hashtags at the end, and be catchy. "
        "Do not add any intro or explanation — only the 5 numbered captions."
    )


def split_message(text, limit=4000):
    """Split a long answer into Telegram-safe chunks, on line boundaries."""
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        piece = line + "\n"
        if len(current) + len(piece) > limit:
            if current:
                chunks.append(current.rstrip("\n"))
                current = ""
            while len(piece) > limit:  # one very long line: hard-split it
                chunks.append(piece[:limit])
                piece = piece[limit:]
        current += piece
    if current.strip():
        chunks.append(current.rstrip("\n"))
    return chunks or [text[:limit]]
