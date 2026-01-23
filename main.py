import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)
from dotenv import load_dotenv

from yclients_client import YclientsClient, YclientsConfig


router = Router()
yclients_client: YclientsClient | None = None


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подтвердить запись", callback_data="confirm_booking"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отменить запись", callback_data="cancel_booking"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Перенести запись", callback_data="reschedule_booking"
                )
            ],
        ]
    )
    await message.answer(
        "Привет! Я бот-менеджер. Напиши /help, чтобы увидеть команды.",
        reply_markup=keyboard,
    )


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    await message.answer("Доступные команды: /start, /help")


@router.callback_query(F.data == "confirm_booking")
async def handle_confirm_booking(callback: CallbackQuery) -> None:
    if not yclients_client or not yclients_client.is_configured():
        await callback.answer("Yclients не настроен", show_alert=True)
        return
    await callback.answer(
        "Интеграция активна, но нет данных для подтверждения записи.",
        show_alert=True,
    )


@router.callback_query(F.data == "cancel_booking")
async def handle_cancel_booking(callback: CallbackQuery) -> None:
    if not yclients_client or not yclients_client.is_configured():
        await callback.answer("Yclients не настроен", show_alert=True)
        return
    await callback.answer(
        "Интеграция активна, но нет данных для отмены записи.",
        show_alert=True,
    )


@router.callback_query(F.data == "reschedule_booking")
async def handle_reschedule_booking(callback: CallbackQuery) -> None:
    if not yclients_client or not yclients_client.is_configured():
        await callback.answer("Yclients не настроен", show_alert=True)
        return
    await callback.answer(
        "Интеграция активна, но нет данных для переноса записи.",
        show_alert=True,
    )


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Не задана переменная окружения BOT_TOKEN")

    global yclients_client
    yclients_client = YclientsClient(YclientsConfig.from_env())

    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_router(router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

