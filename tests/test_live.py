"""Live tests against the real DTZ AI API — no Telegram token needed.

Run:  .venv/bin/python tests/test_live.py
Checks /api/health, a real streamed chat answer, and the exact prompts
the bot's /summarize and /caption commands send.
"""

import asyncio
import os
import sys

import aiohttp

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from dtz_ai import (  # noqa: E402
    build_caption_prompt,
    build_chat_question,
    build_reply_prompt,
    build_summary_prompt,
    check_health,
    stream_chat,
)

RESULTS = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    RESULTS.append(bool(condition))


async def main():
    async with aiohttp.ClientSession(trust_env=True) as session:
        online = await check_health(session, config.API_BASE)
        check("api /api/health online", online)

        q = build_chat_question([], "What is 2 + 2? Answer in one short sentence.")
        answer = await stream_chat(session, config.API_BASE, config.API_KEY, q)
        check("chat streams a real answer", len(answer) > 0 and "4" in answer, repr(answer[:120]))

        q2 = build_chat_question(
            [("user", "What is 2 + 2?"), ("assistant", "2 + 2 is 4.")],
            "And what is 4 + 4?",
        )
        answer2 = await stream_chat(session, config.API_BASE, config.API_KEY, q2)
        check("chat with history answers follow-up", len(answer2) > 0 and "8" in answer2, repr(answer2[:120]))

        summary = await stream_chat(
            session, config.API_BASE, config.API_KEY,
            build_summary_prompt(
                "Pakistan is a country in South Asia. Its capital is Islamabad. "
                "Its largest city is Karachi. Urdu is the national language."
            ),
        )
        check("summarize prompt returns a summary", len(summary) > 20, repr(summary[:120]))

        reply = await stream_chat(
            session, config.API_BASE, config.API_KEY,
            build_reply_prompt("kal milte hain?", "roman"),
        )
        check("reply prompt returns a reply", len(reply) > 5, repr(reply[:120]))

        captions = await stream_chat(
            session, config.API_BASE, config.API_KEY,
            build_caption_prompt("chai time", "instagram"),
        )
        numbered = sum(1 for line in captions.splitlines() if line.strip()[:2] in ("1.", "2.", "3.", "4.", "5."))
        check("caption prompt returns numbered captions", numbered >= 3, f"{numbered}/5 numbered, {len(captions)} chars")

    print(f"\n{sum(RESULTS)}/{len(RESULTS)} live tests passed")
    sys.exit(0 if all(RESULTS) else 1)


if __name__ == "__main__":
    asyncio.run(main())
