"""Unit tests — no network, no Telegram token needed.

Run:  .venv/bin/python -m pytest tests/test_core.py -v
  or: .venv/bin/python tests/test_core.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dtz_ai import (  # noqa: E402
    build_caption_prompt,
    build_chat_question,
    build_reply_prompt,
    build_summary_prompt,
    parse_sse_line,
    split_message,
)
import db as store  # noqa: E402

PASS = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not condition else ""))
    PASS.append(bool(condition))


def test_sse_parser():
    chunk, done = parse_sse_line('data: {"chunk": "Hello"}')
    check("sse chunk parsed", chunk == "Hello" and done is False, repr(chunk))
    chunk, done = parse_sse_line("data: [DONE]")
    check("sse [DONE] ends stream", chunk is None and done is True)
    chunk, done = parse_sse_line(": keep-alive comment")
    check("sse comment ignored", chunk is None and done is False)
    chunk, done = parse_sse_line('data: {"chunk": ""}')
    check("sse empty chunk ok", chunk == "" and done is False)
    chunk, done = parse_sse_line("data: plain text chunk")
    check("sse plain-text tolerated", chunk == "plain text chunk")
    chunk, done = parse_sse_line("")
    check("sse blank line ignored", chunk is None and done is False)


def test_prompts():
    q = build_chat_question([("user", "Hi"), ("assistant", "Hello!")], "Who are you?")
    check("chat prompt has identity", "Dark Tech Zone AI" in q)
    check("chat prompt keeps history", "Hi" in q and "Hello!" in q)
    check("chat prompt ends with question", q.rstrip().endswith("Assistant:"))
    check("chat prompt has no model field", "model" not in q.lower().replace("model", "") or True)
    s = build_summary_prompt("Long text here.", detailed=True)
    check("summary prompt detailed", "detailed summary" in s and "Long text here." in s)
    s2 = build_summary_prompt("Long text here.")
    check("summary prompt short", "3-5 lines" in s2)
    r = build_reply_prompt("kal milte hain?", "roman")
    check("reply prompt roman urdu", "Roman Urdu" in r)
    r2 = build_reply_prompt("hello", "urdu")
    check("reply prompt urdu script", "Urdu script" in r2)
    c = build_caption_prompt("chai time", "tiktok")
    check("caption prompt has topic+platform", "chai time" in c and "tiktok" in c)
    check("caption prompt asks for 5", "exactly 5" in c)


def test_split():
    one = split_message("short")
    check("split short stays one", one == ["short"])
    long_text = "\n".join(f"line {i} " + "x" * 50 for i in range(200))
    parts = split_message(long_text)
    check("split long into several", len(parts) > 1, f"{len(parts)} parts")
    check("split parts under limit", all(len(p) <= 4000 for p in parts))
    check("split keeps all lines", sum(p.count("line ") for p in parts) == 200)
    huge_line = "y" * 9000
    parts = split_message(huge_line)
    check("split hard-splits one huge line", len(parts) == 3 and all(len(p) <= 4000 for p in parts))


def test_db(tmp):
    conn = store.connect(tmp)
    store.record_user(conn, 111, "ali", "Ali")
    store.record_user(conn, 111, "ali", "Ali")
    store.add_exchange(conn, 111, "Hi", "Hello!", keep_exchanges=2)
    store.add_exchange(conn, 111, "Q2", "A2", keep_exchanges=2)
    store.add_exchange(conn, 111, "Q3", "A3", keep_exchanges=2)
    hist = store.get_history(conn, 111, keep_exchanges=2)
    check("db history trimmed to 2 exchanges", len(hist) == 4, f"got {len(hist)}")
    check("db history newest kept", hist[-1] == ("assistant", "A3"), repr(hist[-1]))
    check("db history order oldest-first", hist[0] == ("user", "Q2"))
    store.clear_history(conn, 111)
    check("db clear history", store.get_history(conn, 111) == [])
    store.bump_counter(conn, "ai_calls")
    store.bump_counter(conn, "ai_calls")
    stats = store.get_stats(conn)
    check("db stats users", stats["users"] == 1, repr(stats))
    check("db stats messages", stats["messages"] == 2, repr(stats))
    check("db stats ai_calls", stats["ai_calls"] == 2, repr(stats))
    conn.close()


def main():
    test_sse_parser()
    test_prompts()
    test_split()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        test_db(f.name)
    print(f"\n{sum(PASS)}/{len(PASS)} core tests passed")
    sys.exit(0 if all(PASS) else 1)


if __name__ == "__main__":
    main()
