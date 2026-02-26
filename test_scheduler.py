import asyncio
import logging

from aiogram import Bot

from src.config import settings
from src.database.database import db_manager
from src.services.scheduler import ReminderScheduler

logging.basicConfig(level=logging.INFO)


async def test_check_reminders():
    bot = Bot(token=settings.TELEGRAM_TOKEN)
    scheduler = ReminderScheduler(bot)

    await db_manager.init_db()

    print("Running manual reminder check...")
    await scheduler.check_and_send_reminders()
    print("Check completed")

    await bot.session.close()
    await db_manager.close()


if __name__ == "__main__":
    asyncio.run(test_check_reminders())