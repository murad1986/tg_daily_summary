from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import db
from summarizer import build_messages_block, summarize_messages_text

# Load environment
load_dotenv(override=False)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
SUMMARY_RETENTION_DAYS = int(os.environ.get("SUMMARY_RETENTION_DAYS", "14"))


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None:
        return
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "Привет! Я бот для дневных саммари чата.\n"
            "— Сохраняю все текстовые сообщения.\n"
            "— В 21:00 UTC отправляю краткое саммари за последние 24 часа.\n"
            "— Использую Google Gemini для саммаризации."
        ),
    )


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None:
        return
    if not message.text:
        return

    user = update.effective_user
    user_name: Optional[str] = None
    if user is not None:
        user_name = user.full_name or user.username or str(user.id)

    timestamp = message.date
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    # Получаем message_thread_id для поддержки тем в форумах и каналах
    message_thread_id = getattr(message, 'message_thread_id', None)
    
    db.add_message(
        chat_id=chat.id, 
        user_name=user_name, 
        message_text=message.text, 
        timestamp=timestamp,
        message_thread_id=message_thread_id
    )


async def summarize_messages_for_chat(chat_id: int) -> Optional[str]:
    since_time = datetime.now(timezone.utc) - timedelta(days=1)
    
    # Получаем все активные темы в чате
    thread_ids = db.get_active_thread_ids_for_chat_since(chat_id, since_time)
    
    if not thread_ids:
        return None
    
    # Если есть только одна тема (или основной чат без тем)
    if len(thread_ids) == 1:
        messages = db.get_messages_for_chat_since(chat_id, since_time, thread_ids[0])
        if not messages:
            return None
            
        lines = []
        for m in messages:
            author = m.user_name or "Unknown"
            content = m.message_text.strip().replace("\n", " ")
            lines.append(f"{author}: {content}")

        messages_block = build_messages_block(lines)
        try:
            summary = summarize_messages_text(messages_block)
            return summary
        except Exception as exc:  # noqa: BLE001
            print(f"[summarize_messages_for_chat] Ошибка: {exc}")
            return None
    
    # Если несколько тем - создаём саммари для каждой темы отдельно
    all_summaries = []
    for thread_id in thread_ids:
        messages = db.get_messages_for_chat_since(chat_id, since_time, thread_id)
        if not messages:
            continue
            
        lines = []
        for m in messages:
            author = m.user_name or "Unknown"
            content = m.message_text.strip().replace("\n", " ")
            lines.append(f"{author}: {content}")

        messages_block = build_messages_block(lines)
        try:
            thread_summary = summarize_messages_text(messages_block)
            thread_name = f"Тема {thread_id}" if thread_id else "Основной чат"
            all_summaries.append(f"🔖 **{thread_name}**\n{thread_summary}")
        except Exception as exc:  # noqa: BLE001
            print(f"[summarize_messages_for_chat] Ошибка для темы {thread_id}: {exc}")
            continue
    
    if not all_summaries:
        return None
        
    return "\n\n" + "═" * 50 + "\n\n".join(all_summaries)


async def send_daily_summary(bot: Bot) -> None:
    since_time = datetime.now(timezone.utc) - timedelta(days=1)
    chat_ids = db.get_active_chat_ids_since(since_time)

    for chat_id in chat_ids:
        summary = await summarize_messages_for_chat(chat_id)
        if summary:
            try:
                await bot.send_message(chat_id=chat_id, text=summary[:3800])
            except Exception as exc:  # noqa: BLE001
                print(f"[send_daily_summary] Не удалось отправить саммари в {chat_id}: {exc}")

    try:
        deleted = db.delete_messages_older_than(SUMMARY_RETENTION_DAYS)
        if deleted:
            print(f"[cleanup] Удалено старых сообщений: {deleted}")
    except Exception as exc:  # noqa: BLE001
        print(f"[cleanup] Ошибка очистки: {exc}")


def setup_scheduler(app: Application) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=timezone.utc)

    async def job_wrapper() -> None:
        await send_daily_summary(app.bot)

    scheduler.add_job(
        job_wrapper,
        trigger=CronTrigger(hour=21, minute=0, timezone=timezone.utc),
    )
    scheduler.start()
    return scheduler


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан в окружении")

    db.initialize_database()

    application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    # Текстовые сообщения в группах/супергруппах/личке
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_message))
    # Текстовые посты в каналах (channel_post)
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL & filters.TEXT, handle_text_message))
    # Поддержка форум-групп (сообщения в темах)
    application.add_handler(MessageHandler(filters.ChatType.SUPERGROUP & filters.TEXT & (~filters.COMMAND), handle_text_message))

    setup_scheduler(application)

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
