# Dentist Bot

Бот для напоминаний и управления записями в Dentist Plus через Telegram.
Помогает администратору и клиентам получать актуальный статус записи и уведомления.

## Технологии

- aiogram
- aiogram-dialog
- pydantic
- pydantic-settings

## Установка

Требуется Python 3.10+ (из-за зависимостей `aiogram` и `pydantic`).

1) Клонирование:
```
git clone https://github.com/BogdanMod/DentistBot.git
cd DentistBot
```

2) Установка зависимостей через uv:
```
uv sync
```

3) Создание `.env`:
```
TELEGRAM_TOKEN=your_telegram_bot_token
ADMIN_CHAT_ID=your_admin_id
LOG_LEVEL=INFO
DEBUG=false
DENTIST_PLUS_LOGIN=api_login
DENTIST_PLUS_PASSWORD=api_password
DENTIST_PLUS_BRANCH_ID=1
```

4) Запуск:
```
python3 -m src.bot.main
```

## Напоминания в 10:00

- В `.env` задайте `REMINDER_CHECK_TIME=10:00` и **`REMINDER_TIMEZONE=Europe/Moscow`** (или вашу таймзону), иначе 10:00 будет по UTC.
- После правок **Docker-образ нужно пересобрать** (`docker compose build --no-cache`), в образе должен быть пакет `tzdata` (уже в `dockerfile`), иначе `Europe/Moscow` в контейнере может работать некорректно.
- В логах при старте смотрите строку `next_run=...` — если `None`, джоба не поставилась.
- Если в 10:00 пришло `records_count=0` — в Dentist Plus нет записей на **завтра** (в выбранной таймзоне).
- Если много `Skip record ... no bot user` — клиент не зарегистрирован в боте или не совпал `yclients_client_id`.
