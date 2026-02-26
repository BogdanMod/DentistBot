"""Планировщик автоматических задач"""
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.config import settings
from src.database.crud import ReminderCRUD, UserCRUD
from src.database.database import db_manager
from src.services.notifications import send_reminder_notification
from src.services.yclients import yclients_client

logger = logging.getLogger(__name__)


class ReminderScheduler:
    """Планировщик напоминаний"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()

    async def check_and_send_reminders(self) -> None:
        """
        Проверка и отправка напоминаний.

        Логика:
        1. Получить все записи из YClients на следующие REMINDER_HOURS_BEFORE часов
        2. Для каждой записи найти зарегистрированного пользователя
        3. Создать reminder если ещё не создан
        4. Отправить если ещё не отправлен
        """
        logger.info("Starting reminder check...")

        now = datetime.now(timezone.utc)
        target_time = now + timedelta(hours=settings.REMINDER_HOURS_BEFORE)

        try:
            records = await yclients_client.get_records(
                start_date=now,
                end_date=target_time + timedelta(hours=1),
            )
            logger.info(f"Found {len(records)} records in YClients")

        except Exception as e:
            logger.error(f"Failed to get records from YClients: {str(e)}")
            return

        sent_count = 0
        skipped_count = 0

        for record in records:
            try:
                async for session in db_manager.get_session():
                    user = await UserCRUD.get_by_yclients_client_id(
                        session=session,
                        yclients_client_id=record["client"]["id"],
                    )

                    if not user:
                        logger.debug(f"User not found for client {record['client']['id']}")
                        skipped_count += 1
                        continue

                    existing = await ReminderCRUD.get_by_record_id(
                        session=session,
                        record_id=record["id"],
                    )

                    if existing and existing.is_sent:
                        skipped_count += 1
                        continue

                    if not existing:
                        reminder = await ReminderCRUD.create(
                            session=session,
                            user_chat_id=user.chat_id,
                            record_id=record["id"],
                            appointment_datetime=datetime.fromisoformat(record["datetime"]).replace(tzinfo=timezone.utc).astimezone(),
                            service_name=record["services"][0]["title"] if record.get("services") else "Услуга",
                            staff_name=record["staff"]["name"] if record.get("staff") else "Мастер",
                        )
                    else:
                        reminder = existing

                    success = await send_reminder_notification(
                        bot=self.bot,
                        reminder=reminder,
                    )

                    if success:
                        sent_count += 1
                    else:
                        skipped_count += 1

            except Exception as e:
                logger.error(f"Error processing record {record.get('id')}: {str(e)}", exc_info=True)
                skipped_count += 1

        logger.info(f"Reminder check completed. Sent: {sent_count}, Skipped: {skipped_count}")

    def start(self) -> None:
        """Запуск планировщика"""

        self.scheduler.add_job(
            func=self.check_and_send_reminders,
            # trigger=CronTrigger(minute=0),
            trigger=IntervalTrigger(minutes=1),
            id="check_reminders",
            replace_existing=True,
        )

        logger.info(
            f"Scheduler started. Will check reminders every hour at :00"
        )

        self.scheduler.start()

    def shutdown(self) -> None:
        """Остановка планировщика"""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")