"""Обработчики callback-кнопок"""
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from src.bot.keyboards.inline import create_cancel_reason_keyboard
from src.config import settings
from src.database.crud import (
    NotificationLogCRUD,
    ReminderCRUD,
    RescheduleRequestCRUD,
    UserCRUD,
)
from src.database.database import db_manager
from src.services.yclients import yclients_client

logger = logging.getLogger(__name__)

callback_router = Router()

# Единый контакт и формулировки для пациента
def _admin_contact() -> str:
    return getattr(settings, "RESCHEDULE_CONTACT", "") or "@Shevtsova_team"

MSG_NEW_RECORD = (
    "Администратор свяжется с Вами для новой записи.\n"
)
MSG_RESCHEDULE = (
    "Администратор свяжется с Вами для переноса записи.\n"
)


def _safe_record_id(callback_data: str, prefix: str) -> int | None:
    """Извлекает record_id из callback_data вида prefix_{id} или prefix_{id}_..."""
    if not callback_data or not callback_data.startswith(prefix):
        return None
    rest = callback_data[len(prefix) :].lstrip("_")
    if not rest:
        return None
    first = rest.split("_")[0]
    try:
        return int(first)
    except ValueError:
        return None


async def _safe_edit_message(callback: CallbackQuery, text: str, **kwargs) -> None:
    """edit_text без падения, если сообщение уже изменено/удалено."""
    if callback.message is None:
        return
    try:
        await callback.message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return
        logger.warning(f"edit_text skipped: {e}")
        try:
            await callback.message.answer(text)
        except Exception:
            pass


@callback_router.callback_query(F.data.startswith("confirm_"))
async def handle_confirm_appointment(callback: CallbackQuery) -> None:
    """Обработка подтверждения записи"""
    await callback.answer()

    record_id = _safe_record_id(callback.data, "confirm")
    if record_id is None:
        await callback.answer("Некорректные данные", show_alert=True)
        return

    # Обновляем статус в YClients
    success = await yclients_client.update_record_status(
        record_id=record_id,
        status="confirmed",
        comment="Подтверждено пациентом через Telegram бота",
    )

    if success:
        # Обновляем статус в БД
        async for session in db_manager.get_session():
            await ReminderCRUD.mark_as_confirmed(session, record_id)

            # Логируем уведомление
            await NotificationLogCRUD.log_notification(
                session=session,
                chat_id=callback.from_user.id,
                message_type="confirmation",
                record_id=record_id,
                is_successful=True,
            )

        base = callback.message.text if callback.message else ""
        await _safe_edit_message(
            callback,
            f"{base}\n\n"
            "✅ Запись подтверждена!\n"
            "Ждем вас в назначенное время. 😊",
        )

        logger.info(f"Record {record_id} confirmed by user {callback.from_user.id}")
    else:
        await callback.message.answer(
            "❌ Не удалось подтвердить запись. "
            "Пожалуйста, попробуйте позже.\n\n"
            f"{MSG_NEW_RECORD}{_admin_contact()}"
        )
        
@callback_router.callback_query(F.data.startswith("cancel_") & ~ F.data.startswith("cancel_reason"))
async def handle_cancel_appointment(callback: CallbackQuery) -> None:
    """Обработка отмены записи"""
    await callback.answer()

    record_id = _safe_record_id(callback.data, "cancel")
    if record_id is None:
        await callback.answer("Некорректные данные", show_alert=True)
        return

    # Показываем клавиатуру с причинами отмены
    base = callback.message.text if callback.message else ""
    await _safe_edit_message(
        callback,
        f"{base}\n\n"
        "Пожалуйста, укажите причину отмены:",
        reply_markup=create_cancel_reason_keyboard(record_id),
    )


@callback_router.callback_query(F.data.startswith("cancel_reason_"))
async def handle_cancel_reason(callback: CallbackQuery) -> None:
    """Обработка выбора причины отмены"""
    await callback.answer()

    # Парсим callback_data: cancel_reason_{record_id}_{reason}
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("Некорректные данные", show_alert=True)
        return
    try:
        record_id = int(parts[2])
    except ValueError:
        await callback.answer("Некорректные данные", show_alert=True)
        return
    reason = "_".join(parts[3:])

    # Словарь причин
    reasons = {
        "ill": "Плохое самочувствие",
        "busy": "Занят/Занята",
        "other": "Другая причина",
    }

    reason_text = reasons.get(reason, "Не указана")

    # Отменяем запись в YClients
    success = await yclients_client.update_record_status(
        record_id=record_id,
        status="deleted",
        comment=f"Отменено пациентом: {reason_text}",
    )

    if success:
        # Обновляем статус в БД
        async for session in db_manager.get_session():
            await ReminderCRUD.mark_as_cancelled(session, record_id)

            # Логируем уведомление
            await NotificationLogCRUD.log_notification(
                session=session,
                chat_id=callback.from_user.id,
                message_type="cancellation",
                record_id=record_id,
                is_successful=True,
            )

        base = ""
        if callback.message and callback.message.text:
            base = callback.message.text.split("Пожалуйста")[0]
        await _safe_edit_message(
            callback,
            f"{base}\n"
            "❌ Запись отменена.\n\n"
            f"Причина: {reason_text}\n\n"
            f"{MSG_NEW_RECORD}{_admin_contact()}",
        )

        logger.info(
            f"Record {record_id} cancelled by user {callback.from_user.id}. "
            f"Reason: {reason_text}"
        )
    else:
        await callback.message.answer(
            "❌ Не удалось отменить запись. "
            "Пожалуйста, попробуйте позже.\n\n"
            f"{MSG_NEW_RECORD}{_admin_contact()}"
        )
        
@callback_router.callback_query(F.data.startswith("reschedule_"))
async def handle_reschedule_appointment(callback: CallbackQuery) -> None:
    """Обработка переноса записи"""
    await callback.answer()

    record_id = _safe_record_id(callback.data, "reschedule")
    if record_id is None:
        await callback.answer("Некорректные данные", show_alert=True)
        return

    # Получаем данные пользователя и записи
    async for session in db_manager.get_session():
        user = await UserCRUD.get_by_chat_id(session, callback.from_user.id)
        reminder = await ReminderCRUD.get_by_record_id(session, record_id)

        if user and reminder:
            # Создаем запрос на перенос
            await RescheduleRequestCRUD.create(
                session=session,
                record_id=record_id,
                user_chat_id=callback.from_user.id,
                original_datetime=reminder.appointment_datetime,
                client_phone=user.phone,
                client_name=user.full_name or "Не указано",
                service_name=reminder.service_name,
            )

            # Уведомляем клиента (именно для переноса записи)
            base = callback.message.text if callback.message else ""
            await _safe_edit_message(
                callback,
                f"{base}\n\n"
                f"🔄 {MSG_RESCHEDULE}{_admin_contact()}",
            )

            # Уведомляем администратора
            doctor_name = (reminder.staff_name or "Доктор").strip()
            if doctor_name.lower() == "мастер":
                doctor_name = "Доктор"
            admin_message = (
                "🔔 Новый запрос на перенос записи\n\n"
                f"📋 ID записи: {record_id}\n"
                f"👤 Пациент: {user.full_name}\n"
                f"📞 Телефон: {user.phone}\n"
                f"Доктор: {doctor_name}\n"
                f"📅 Текущая дата: {reminder.appointment_datetime.strftime('%d.%m.%Y %H:%M')}\n\n"
                "Пожалуйста, свяжитесь с пациентом для уточнения новой даты."
            )

            try:
                await callback.bot.send_message(
                    chat_id=settings.ADMIN_CHAT_ID,
                    text=admin_message,
                )
            except Exception as e:
                logger.error(f"Failed to send admin notification: {str(e)}")

            # Логируем уведомление
            await NotificationLogCRUD.log_notification(
                session=session,
                chat_id=callback.from_user.id,
                message_type="reschedule_request",
                record_id=record_id,
                is_successful=True,
            )

            logger.info(
                f"Reschedule request created for record {record_id} "
                f"by user {callback.from_user.id}"
            )
        else:
            await callback.message.answer(
                "❌ Не удалось создать запрос на перенос. "
                "Пожалуйста, попробуйте позже."
            )