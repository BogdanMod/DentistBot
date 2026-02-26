"""Обработчики команд"""
import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram_dialog import DialogManager, StartMode

from src.bot.dialogs.states import RegistrationStates
from src.database.crud import UserCRUD
from src.database.database import db_manager
from src.services.yclients import yclients_client

logger = logging.getLogger(__name__)
commands_router = Router()


@commands_router.message(CommandStart())
async def start_command(message: Message) -> None:
    """Обработчик команды /start"""
    async for session in db_manager.get_session():
        user = await UserCRUD.get_by_chat_id(session, message.from_user.id)

    if user and user.is_registered:
        await message.answer(f"С возвращением, {user.full_name}!")
        return

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Поделиться номером", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await message.answer(
        "Добро пожаловать!\n\n"
        "Для получения напоминаний о визитах нажмите кнопку ниже:",
        reply_markup=keyboard,
    )


@commands_router.message(F.contact)
async def contact_handler(message: Message, dialog_manager: DialogManager) -> None:
    """Обработчик полученного контакта"""
    contact = message.contact
    phone = contact.phone_number

    # Нормализация номера
    digits = ''.join(filter(str.isdigit, phone))
    if not digits.startswith('7'):
        digits = '7' + digits
    normalized = '+' + digits

    await message.answer("Ищу вас в системе...")

    client_data = await yclients_client.find_client(phone=normalized)

    if not client_data:
        client_data = await yclients_client.find_client(phone=digits)

    if client_data:
        await dialog_manager.start(
            state=RegistrationStates.waiting_for_confirmation,
            mode=StartMode.RESET_STACK,
            data={
                "phone": normalized,
                "full_name": client_data.get("name", ""),
                "email": client_data.get("email", ""),
                "yclients_client_id": client_data.get("id"),
            },
        )
    else:
        await message.answer(
            "Не удалось найти вас в системе.\n"
            "Свяжитесь с администратором салона.",
            reply_markup=ReplyKeyboardRemove(),
        )


@commands_router.message(F.text == "/today")
async def today_command(message: Message) -> None:
    """Показать записи на сегодня"""
    async for session in db_manager.get_session():
        user = await UserCRUD.get_by_chat_id(session, message.from_user.id)

    if not user or not user.is_registered:
        await message.answer("Вы не зарегистрированы.\nИспользуйте /start для регистрации.")
        return

    await message.answer("Функция в разработке.")
