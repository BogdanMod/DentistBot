"""Диалог регистрации пользователя"""
from typing import Any

from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.kbd import Button, Row
from aiogram_dialog.widgets.text import Const, Format

from src.bot.dialogs.states import RegistrationStates
from src.database.crud import UserCRUD
from src.database.database import db_manager


async def confirm_registration(
    callback: CallbackQuery,
    button: Button,
    dialog_manager: DialogManager,
) -> None:
    """Подтверждение регистрации"""
    phone = dialog_manager.dialog_data.get("phone")
    full_name = dialog_manager.dialog_data.get("full_name")
    email = dialog_manager.dialog_data.get("email")
    yclients_client_id = dialog_manager.dialog_data.get("yclients_client_id")

    async for session in db_manager.get_session():
        try:
            await UserCRUD.create(
                session=session,
                chat_id=callback.from_user.id,
                phone=phone,
                full_name=full_name,
                email=email,
                yclients_client_id=yclients_client_id,
            )
            await callback.message.answer(
                f"Регистрация завершена!\n\n"
                f"Имя: {full_name}\n"
                f"Телефон: {phone}\n\n"
                f"Теперь вы будете получать напоминания о предстоящих визитах.",
                reply_markup=ReplyKeyboardRemove(),
            )
        except Exception as e:
            await callback.message.answer(
                "Произошла ошибка при регистрации. Попробуйте позже.",
                reply_markup=ReplyKeyboardRemove(),
            )

    await dialog_manager.done()


async def cancel_registration(
    callback: CallbackQuery,
    button: Button,
    dialog_manager: DialogManager,
) -> None:
    """Отмена регистрации"""
    await callback.message.answer(
        "Регистрация отменена.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await dialog_manager.done()


async def get_registration_data(dialog_manager: DialogManager, **kwargs) -> dict[str, Any]:
    """Получение данных для окна подтверждения"""
    start_data = dialog_manager.start_data or {}
    if not dialog_manager.dialog_data.get("phone"):
        dialog_manager.dialog_data.update(start_data)
    return {
        "full_name": dialog_manager.dialog_data.get("full_name", ""),
        "phone": dialog_manager.dialog_data.get("phone", ""),
    }


registration_dialog = Dialog(
    Window(
        Format(
            "Найдена запись:\n\n"
            "Имя: {full_name}\n"
            "Телефон: {phone}\n\n"
            "Все верно?"
        ),
        Row(
            Button(
                Const("Да, все верно"),
                id="confirm_registration",
                on_click=confirm_registration,
            ),
            Button(
                Const("Отмена"),
                id="cancel_registration",
                on_click=cancel_registration,
            ),
        ),
        state=RegistrationStates.waiting_for_confirmation,
        getter=get_registration_data,
    ),
)
