"""Обработчики callback-кнопок"""
import logging

from aiogram import F, Router
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


@callback_router.callback_query(F.data.startswith("confirm_"))
async def handle_confirm_appointment(callback: CallbackQuery) -> None:
    """Обработка подтверждения записи"""
    await callback.answer()

    # Извлекаем record_id из callback_data
    record_id = int(callback.data.split("_")[1])

    # Обновляем статус в YClients
    success = await yclients_client.update_record_status(
        record_id=record_id,
        status="confirmed",
        comment="Подтверждено клиентом через Telegram бота",
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

        await callback.message.edit_text(
            f"{callback.message.text}\n\n"
            "✅ Запись подтверждена!\n"
            "Ждем вас в назначенное время. 😊"
        )

        logger.info(f"Record {record_id} confirmed by user {callback.from_user.id}")
    else:
        await callback.message.answer(
            "❌ Не удалось подтвердить запись. "
            "Пожалуйста, попробуйте позже или свяжитесь с админом."
        )
        
@callback_router.callback_query(F.data.startswith("cancel_") & ~ F.data.startswith("cancel_reason"))
async def handle_cancel_appointment(callback: CallbackQuery) -> None:
    """Обработка отмены записи"""
    await callback.answer()

    record_id = int(callback.data.split("_")[1])

    # Показываем клавиатуру с причинами отмены
    await callback.message.edit_text(
        f"{callback.message.text}\n\n"
        "Пожалуйста, укажите причину отмены:",
        reply_markup=create_cancel_reason_keyboard(record_id),
    )


@callback_router.callback_query(F.data.startswith("cancel_reason_"))
async def handle_cancel_reason(callback: CallbackQuery) -> None:
    """Обработка выбора причины отмены"""
    await callback.answer()

    # Парсим callback_data: cancel_reason_{record_id}_{reason}
    parts = callback.data.split("_")
    record_id = int(parts[2])
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
        comment=f"Отменено клиентом: {reason_text}",
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

        await callback.message.edit_text(
            f"{callback.message.text.split('Пожалуйста')[0]}\n"
            "❌ Запись отменена.\n\n"
            f"Причина: {reason_text}\n\n"
            "Для новой записи свяжитесь с салоном."
        )

        logger.info(
            f"Record {record_id} cancelled by user {callback.from_user.id}. "
            f"Reason: {reason_text}"
        )
    else:
        await callback.message.answer(
            "❌ Не удалось отменить запись. "
            "Пожалуйста, попробуйте позже или свяжитесь с салоном."
        )
        
@callback_router.callback_query(F.data.startswith("reschedule_"))
async def handle_reschedule_appointment(callback: CallbackQuery) -> None:
    """Обработка переноса записи"""
    await callback.answer()

    record_id = int(callback.data.split("_")[1])

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

            # Уведомляем клиента
            await callback.message.edit_text(
                f"{callback.message.text}\n\n"
                "🔄 Запрос на перенос отправлен!\n\n"
                "Менеджер салона свяжется с вами в ближайшее время "
                "для уточнения новой даты и времени."
            )

            # Уведомляем администратора
            admin_message = (
                "🔔 Новый запрос на перенос записи\n\n"
                f"📋 ID записи: {record_id}\n"
                f"👤 Клиент: {user.full_name}\n"
                f"📞 Телефон: {user.phone}\n"
                f"💇‍♀️ Услуга: {reminder.service_name}\n"
                f"👩 Мастер: {reminder.staff_name}\n"
                f"📅 Текущая дата: {reminder.appointment_datetime.strftime('%d.%m.%Y %H:%M')}\n\n"
                "Пожалуйста, свяжитесь с клиентом для уточнения новой даты."
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