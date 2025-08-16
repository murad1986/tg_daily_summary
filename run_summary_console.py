from __future__ import annotations

from datetime import datetime, timedelta, timezone

import db
from summarizer import build_messages_block, summarize_messages_text


def main() -> None:
    since_time = datetime.now(timezone.utc) - timedelta(days=1)
    chat_ids = db.get_active_chat_ids_since(since_time)

    if not chat_ids:
        print("Нет активных чатов за последние 24 часа.")
        return

    for chat_id in chat_ids:
        messages = db.get_messages_for_chat_since(chat_id, since_time)
        if not messages:
            continue

        lines = []
        for m in messages:
            author = m.user_name or "Unknown"
            content = m.message_text.strip().replace("\n", " ")
            lines.append(f"{author}: {content}")

        block = build_messages_block(lines)
        try:
            summary = summarize_messages_text(block)
        except Exception as exc:  # noqa: BLE001
            print(f"[{chat_id}] Ошибка саммаризации: {exc}")
            continue

        print(f"\n=== Саммари для чата {chat_id} ===\n{summary}\n")


if __name__ == "__main__":
    main()


