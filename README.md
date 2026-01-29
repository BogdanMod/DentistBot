# YClients Dentist Bot

Бот для напоминаний и управления записями в YClients через Telegram.
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
ADMIN_ID=your_admin_id
LOG_LEVEL=INFO
DEBUG=false
```

4) Запуск:
```
python3 -m src.bot.main
```
