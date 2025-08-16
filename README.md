## Telegram Chat Daily Summary Bot (Gemini, SQLite, APScheduler)

Локальный Telegram-бот, который собирает сообщения из группового чата, раз в день (21:00 UTC) делает краткое саммари через Google Gemini и отправляет результат в тот же чат.

### Возможности
- Сбор всех текстовых сообщений из групповых чатов, каналов и форумов
- **🆕 Поддержка тем (topics)** в форум-группах и каналах — отдельные саммари для каждой темы
- Хранение в SQLite (`chat_logs.db`) с поддержкой message_thread_id
- Ежедневная саммаризация за последние 24 часа (21:00 UTC) с помощью Google Gemini
- Планировщик задач — APScheduler
- Минимальная инфраструктура: локальный запуск / Docker

### Требования
- Python 3.12+
- Переменные окружения: `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`

### Установка и запуск (Docker — рекомендуемо)
1. Создайте бота через @BotFather, отключите режим приватности (Bot Settings → Group Privacy → Turn off)
2. Получите API ключ Gemini и сохраните его
3. Создайте файл `.env` в корне по шаблону:
   ```env
   TELEGRAM_BOT_TOKEN=123456:ABC...
   GEMINI_API_KEY=your_gemini_key
   GEMINI_MODEL_NAME=gemini-1.5-flash
   SUMMARY_RETENTION_DAYS=14
   ```
4. Запуск:
   ```bash
   docker compose up --build
   ```
5. Добавьте бота в групповой чат, дайте права читать сообщения

### Ручной запуск саммари (разово)
- В консоль (для всех активных чатов за 24 часа):
  ```bash
  docker compose run --rm bot python run_summary_console.py
  ```
- Отправить в Telegram (нужен `TELEGRAM_BOT_TOKEN`):
  ```bash
  docker compose run --rm bot python run_summary_send.py
  ```
- Тестирование поддержки тем:
  ```bash
  docker compose run --rm bot python test_threads.py
  ```

### Локальный запуск без Docker
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

### Структура
- `bot.py` — основной скрипт бота
- `db.py` — SQLite (инициализация, запись/чтение, очистка)
- `summarizer.py` — интеграция с Gemini, промпт
- `requirements.txt` — зависимости
- `.env.example` — шаблон окружения
- `docker-compose.yml`, `Dockerfile` — контейнеризация

### Как это работает
- Бот слушает все текстовые сообщения, каждое сохраняется: `id, chat_id, message_thread_id, user_name, message_text, timestamp`
- В 21:00 UTC собираются сообщения за 24 часа по каждой теме отдельно
- **Для форумов/каналов с темами:** создаётся отдельное саммари для каждой активной темы
- **Для обычных чатов:** создаётся общее саммари как раньше
- Результат отправляется в тот же чат (или тему, если это форум)
- Очистка старых записей (по умолчанию 14 дней)

### Примечания
- Время контейнера — UTC (`TZ=UTC`)
- Если за сутки не было сообщений в чате — отправки не будет
- Для отладки можно изменить расписание/хранение через переменные окружения

### Лицензия
MIT
