import asyncio
import logging
import re
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from src.config import settings


bot = Bot(token=settings.TELEGRAM_TOKEN)
dp = Dispatcher()
logger = logging.getLogger(__name__)


def get_project_version() -> str:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        content = pyproject_path.read_text(encoding="utf-8")
    except OSError:
        return "unknown"
    match = re.search(r'^\s*version\s*=\s*"([^"]+)"\s*$', content, re.MULTILINE)
    return match.group(1) if match else "unknown"


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else "unknown"
    logger.info("Получена команда /start от пользователя %s", user_id)
    first_name = message.from_user.first_name if message.from_user else "друг"
    await message.answer(
        f"Привет, {first_name}!\n"
        "Я бот-менеджер стоматологии и помогу с записями.\n"
        "Могу подсказать доступные услуги, время и статус ваших записей.\n"
        "Напишите /help, чтобы увидеть доступные команды."
    )


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Доступные команды:\n"
        "/start — приветствие и краткая информация о боте\n"
        "/help — список команд и описание\n"
        "/about — информация о боте"
    )


@dp.message(Command("about"))
async def cmd_about(message: Message) -> None:
    version = get_project_version()
    await message.answer(
        "YClients Dentist Bot\n"
        f"Версия: {version}\n"
        "Автор: Uncknown"
    )


async def main() -> None:
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logger.info("Бот запускается...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

