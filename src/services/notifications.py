"""Сервис отправки уведомлений"""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from src.database.crud import NotificationLogCRUD, ReminderCRUD
from src.database.database import db_manager
from src.database.models import Reminder

logger = logging.getLogger(__name__)


async def send_reminder_notification(bot: Bot, reminder: Reminder) -> bool:
    """
    Отправить напоминание пользователю.

    Returns:
        True если успешно, False если ошибка
    """
    try:
        text = (
            f"Напоминание о записи\n\n"
            f"Дата: {reminder.appointment_datetime.strftime('%d.%m.%Y %H:%M')}\n"
            f"Услуга: {reminder.service_name}\n"
            f"Мастер: {reminder.staff_name}\n\n"
            f"Подтвердите или отмените запись."
        )

        from src.bot.keyboards.inline import create_reminder_keyboard
        keyboard = create_reminder_keyboard(reminder.id)

        await bot.send_message(
            chat_id=reminder.user_chat_id,
            text=text,
            reply_markup=keyboard,
        )

        async for session in db_manager.get_session():
            await ReminderCRUD.mark_as_sent(session=session, reminder_id=reminder.id)
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