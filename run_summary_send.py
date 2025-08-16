from __future__ import annotations

import os
import asyncio
from datetime import datetime, timedelta, timezone

from telegram import Bot

import db
from summarizer import build_messages_block, summarize_messages_text


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


async def send_for_chat(bot: Bot, chat_id: int) -> None:
    since_time = datetime.now(timezone.utc) - timedelta(days=1)
    messages = db.get_messages_for_chat_since(chat_id, since_time)
    if not messages:
        return

    lines = []
    for m in messages:
        author = m.user_name or "Unknown"
        content = m.message_text.strip().replace("\n", " ")
        lines.append(f"{author}: {content}")

    block = build_messages_block(lines)
    summary = summarize_messages_text(block)
    await bot.send_message(chat_id=chat_id, text=summary[:3800])


async def main_async() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан в окружении")

    since_time = datetime.now(timezone.utc) - timedelta(days=1)
    chat_ids = db.get_active_chat_ids_since(since_time)
    if not chat_ids:
        print("Нет активных чатов за последние 24 часа.")
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    for chat_id in chat_ids:
        try:
            await send_for_chat(bot, chat_id)
            print(f"Отправлено саммари в чат {chat_id}")
        except Exception as exc:  # noqa: BLE001
            print(f"Не удалось отправить саммари в {chat_id}: {exc}")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()


