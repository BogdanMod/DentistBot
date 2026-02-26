"""Точка входа в бот"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram_dialog import setup_dialogs

from src.bot.dialogs.registration import registration_dialog
from src.bot.handlers.commands import commands_router
from src.config import settings

from src.database.database import db_manager
from src.bot.handlers.callbacks import callback_router

from src.services.scheduler import ReminderScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

bot = Bot(token=settings.TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
scheduler = ReminderScheduler(bot)


async def main() -> None:
    """Главная функция запуска бота"""
    try:
        # 1. Инициализация БД
        await db_manager.init_db()
        logger.info("Database initialized")

        # Делаем scheduler доступным в хендлерах через DI.
        dp["scheduler"] = scheduler

        # 2. Регистрация handlers
        dp.include_router(commands_router)
        dp.include_router(callback_router)

        # 3. Регистрация dialogs
        dp.include_router(registration_dialog)

        # 4. Setup aiogram-dialog
        setup_dialogs(dp)

        # 5. Запуск планировщика
        scheduler.start()
        logger.info("Scheduler started")

        logger.info("Bot started")
        await dp.start_polling(bot)

    finally:
        scheduler.shutdown()
        await bot.session.close()
        await db_manager.close()
        await yclients_clients.close()


if __name__ == "__main__":
    asyncio.run(main())
