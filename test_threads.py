#!/usr/bin/env python3
"""
Скрипт для тестирования поддержки тем (threads) в каналах и форумах.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

import db
from summarizer import build_messages_block, summarize_messages_text


def test_database_structure():
    """Проверить структуру базы данных с поддержкой тем."""
    print("🔍 Проверка структуры базы данных...")
    
    with db.get_connection() as conn:
        # Проверяем структуру таблицы
        cur = conn.execute("PRAGMA table_info(messages);")
        columns = cur.fetchall()
        
        print("📋 Колонки таблицы messages:")
        for col in columns:
            print(f"   {col[1]} ({col[2]}) - {'NOT NULL' if col[3] else 'NULL'}")
        
        # Проверяем индексы
        cur = conn.execute("PRAGMA index_list(messages);")
        indexes = cur.fetchall()
        
        print("\n📊 Индексы:")
        for idx in indexes:
            print(f"   {idx[1]} ({'UNIQUE' if idx[2] else 'NON-UNIQUE'})")


def add_test_messages():
    """Добавить тестовые сообщения с разными thread_id."""
    print("\n📝 Добавление тестовых сообщений...")
    
    test_chat_id = -1001234567890  # Тестовый форум-чат
    now = datetime.now(timezone.utc)
    
    # Сообщения в основном чате (без темы)
    db.add_message(test_chat_id, "Алиса", "Общее объявление для всех", now)
    db.add_message(test_chat_id, "Боб", "Согласен с объявлением", now)
    
    # Сообщения в теме 1 (Техподдержка)
    db.add_message(test_chat_id, "Клиент1", "У меня проблема с заказом #123", now, message_thread_id=1)
    db.add_message(test_chat_id, "Поддержка", "Проверяем ваш заказ", now, message_thread_id=1)
    db.add_message(test_chat_id, "Клиент1", "Спасибо за помощь!", now, message_thread_id=1)
    
    # Сообщения в теме 2 (Разработка)
    db.add_message(test_chat_id, "Разработчик1", "Релиз готов к тестированию", now, message_thread_id=2)
    db.add_message(test_chat_id, "Тестировщик", "Начинаю тестирование функций", now, message_thread_id=2)
    db.add_message(test_chat_id, "Разработчик1", "Исправил найденные баги", now, message_thread_id=2)
    
    print("✅ Добавлено 8 тестовых сообщений")


def test_thread_queries():
    """Протестировать запросы с поддержкой тем."""
    print("\n🔍 Тестирование запросов с темами...")
    
    test_chat_id = -1001234567890
    since_time = datetime.now(timezone.utc)
    
    # Получаем все активные темы
    thread_ids = db.get_active_thread_ids_for_chat_since(test_chat_id, since_time)
    print(f"📋 Активные темы: {thread_ids}")
    
    # Проверяем сообщения по темам
    for thread_id in thread_ids:
        messages = db.get_messages_for_chat_since(test_chat_id, since_time, thread_id)
        thread_name = f"Тема {thread_id}" if thread_id else "Основной чат"
        print(f"\n🔖 {thread_name} ({len(messages)} сообщений):")
        
        for msg in messages:
            print(f"   {msg.user_name}: {msg.message_text}")


async def test_summarization():
    """Протестировать создание саммари для разных тем."""
    print("\n📊 Тестирование саммаризации по темам...")
    
    from bot import summarize_messages_for_chat
    
    test_chat_id = -1001234567890
    
    try:
        summary = await summarize_messages_for_chat(test_chat_id)
        if summary:
            print("✅ Саммари создано:")
            print(summary)
        else:
            print("❌ Саммари не создано")
    except Exception as e:
        print(f"❌ Ошибка при создании саммари: {e}")


def cleanup_test_data():
    """Очистить тестовые данные."""
    print("\n🧹 Очистка тестовых данных...")
    
    test_chat_id = -1001234567890
    
    with db.get_connection() as conn:
        cur = conn.execute("DELETE FROM messages WHERE chat_id = ?", (test_chat_id,))
        deleted = cur.rowcount
        conn.commit()
        
    print(f"✅ Удалено {deleted} тестовых сообщений")


async def main():
    """Главная функция тестирования."""
    print("🚀 Тестирование поддержки тем в Telegram-боте")
    print("=" * 50)
    
    # Инициализируем базу данных
    db.initialize_database()
    
    # Тестируем структуру БД
    test_database_structure()
    
    # Добавляем тестовые данные
    add_test_messages()
    
    # Тестируем запросы
    test_thread_queries()
    
    # Тестируем саммаризацию (только если есть API ключ)
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        await test_summarization()
    else:
        print("\n⚠️  GEMINI_API_KEY не задан, пропускаем тест саммаризации")
    
    # Очищаем тестовые данные
    cleanup_test_data()
    
    print("\n✅ Все тесты завершены!")


if __name__ == "__main__":
    asyncio.run(main())
