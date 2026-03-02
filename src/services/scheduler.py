"""Планировщик автоматических задач"""
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

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

    @staticmethod
    def _parse_reminder_time() -> tuple[int, int]:
        """Парсит REMINDER_CHECK_TIME (формат HH:MM) в (hour, minute)."""
        raw = settings.REMINDER_CHECK_TIME.strip()
        if ":" in raw:
            h, m = raw.split(":", 1)
            return int(h.strip()), int(m.strip())
        return 10, 0

    async def check_and_send_reminders(self) -> None:
        """
        Проверка и отправка напоминаний.

        Логика:
        1. Получить все записи из YClients на завтра (следующий календарный день в REMINDER_TIMEZONE)
        2. Для каждой записи найти зарегистрированного пользователя
        3. Создать reminder если ещё не создан
        4. Отправить если ещё не отправлен
        """
        logger.info("Starting reminder check...")

        tz = ZoneInfo(settings.REMINDER_TIMEZONE)
        now = datetime.now(tz)
        tomorrow = (now.date() + timedelta(days=1))
        start_date = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0, tzinfo=tz)
        end_date = start_date + timedelta(days=1) - timedelta(seconds=1)

        try:
            records = await yclients_client.get_records(
                start_date=start_date,
                end_date=end_date,
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
        """Запуск планировщика: раз в день в REMINDER_CHECK_TIME по REMINDER_TIMEZONE."""
        hour, minute = self._parse_reminder_time()

        self.scheduler.add_job(
            func=self.check_and_send_reminders,
            trigger=CronTrigger(
                hour=hour,
                minute=minute,
                timezone=ZoneInfo(settings.REMINDER_TIMEZONE),
            ),
            id="check_reminders",
            replace_existing=True,
        )

        logger.info(
            f"Scheduler started. Reminders at {hour:02d}:{minute:02d} ({settings.REMINDER_TIMEZONE}) for next-day appointments"
        )

        self.scheduler.start()

    def shutdown(self) -> None:
        """Остановка планировщика"""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")