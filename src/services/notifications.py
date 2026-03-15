"""Сервис отправки уведомлений"""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from src.config import settings
from src.database.crud import NotificationLogCRUD, ReminderCRUD
from src.database.database import db_manager
from src.database.models import Reminder

logger = logging.getLogger(__name__)


# Адрес клиники всегда один и тот же
CLINIC_BLOCK = (
    "📍Клиника «Лотос»\n"
    "БЦ Останкино, Огородный проезд, дом 16/1, корпус 3, этаж 11."
)


def _reminder_text(reminder: Reminder) -> str:
    """Текст напоминания о записи по шаблону."""
    appt = reminder.appointment_datetime
    if appt.tzinfo is None:
        from datetime import timezone as tz_module

        appt = appt.replace(tzinfo=tz_module.utc)
    date_str = appt.strftime("%d.%m.%Y в %H:%M")
    signature = getattr(settings, "REMINDER_SIGNATURE", None) or "команда доктора Шевцовой🦷"
    doctor_name = (reminder.staff_name or "Доктор").strip()
    if doctor_name.lower() == "мастер":
        doctor_name = "Доктор"

    return (
        "✋ Добрый день!\n\n"
        "📆 Напоминаем о записи.\n"
        f"{date_str}.\n"
        f"Доктор: {doctor_name}.\n"
        f"{CLINIC_BLOCK}\n\n"
        "Подтверждаете запись?\n\n"
        f"С уважением,\n{signature}"
    )


async def send_reminder_notification(bot: Bot, reminder: Reminder) -> bool:
    """
    Отправить напоминание пользователю.

    Returns:
        True если успешно, False если ошибка
    """
    try:
        text = _reminder_text(reminder)

        from src.bot.keyboards.inline import create_reminder_keyboard
        keyboard = create_reminder_keyboard(reminder.record_id)

        await bot.send_message(
            chat_id=reminder.user_chat_id,
            text=text,
            reply_markup=keyboard,
        )

        async for session in db_manager.get_session():
            await ReminderCRUD.mark_as_sent(session=session, record_id=reminder.record_id)
            await NotificationLogCRUD.log_notification(
                session=session,
                chat_id=reminder.user_chat_id,
                message_type="reminder",
                record_id=reminder.record_id,
                is_successful=True,
            )

        logger.info(f"Reminder {reminder.id} sent to {reminder.user_chat_id}")
        return True

    except TelegramForbiddenError:
        logger.warning(f"User {reminder.user_chat_id} blocked the bot")
        return False

    except TelegramBadRequest as e:
        logger.error(f"Bad request for reminder {reminder.id}: {str(e)}")
        return False

    except Exception as e:
        logger.error(
            f"Failed to send reminder {reminder.id}: {str(e)}",
            exc_info=True,
        )

        try:
            async for session in db_manager.get_session():
                await NotificationLogCRUD.log_notification(
                    session=session,
                    chat_id=reminder.user_chat_id,
                    message_type="reminder",
                    record_id=reminder.record_id,
                    is_successful=False,
                    error_message=str(e),
                )
        except Exception as log_error:
            logger.error(f"Failed to log notification error: {str(log_error)}")

        return False