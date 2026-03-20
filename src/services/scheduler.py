"""Планировщик автоматических задач"""
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import settings
from src.database.crud import ReminderCRUD, UserCRUD
from src.database.database import db_manager
from src.services.notifications import send_reminder_notification
from src.services.admin_report import send_admin_report_for_date
from src.services.yclients import yclients_client
from src.utils.record_helpers import (
    record_appointment_datetime,
    record_client_id,
    record_id as record_id_safe,
    record_service_name,
    record_staff_name,
)

logger = logging.getLogger(__name__)


class ReminderScheduler:
    """Планировщик напоминаний"""

    def __init__(self, bot: Bot):
        self.bot = bot
        # Явная таймзона планировщика — иначе CronTrigger может считать next_run_time не так, как ожидается
        try:
            tz = ZoneInfo(settings.REMINDER_TIMEZONE or "UTC")
        except Exception:
            logger.warning("Invalid REMINDER_TIMEZONE, falling back to UTC")
            tz = ZoneInfo("UTC")
        self.scheduler = AsyncIOScheduler(timezone=tz)

    @staticmethod
    def _parse_reminder_time() -> tuple[int, int]:
        """Парсит REMINDER_CHECK_TIME (формат HH:MM) в (hour, minute)."""
        try:
            raw = (settings.REMINDER_CHECK_TIME or "10:00").strip()
            if ":" in raw:
                h, m = raw.split(":", 1)
                hour = max(0, min(23, int(h.strip())))
                minute = max(0, min(59, int(m.strip())))
                return hour, minute
        except (ValueError, TypeError, AttributeError):
            pass
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

        try:
            tz = ZoneInfo(settings.REMINDER_TIMEZONE or "UTC")
        except Exception:
            tz = ZoneInfo("UTC")
        now = datetime.now(tz)
        tomorrow = now.date() + timedelta(days=1)
        start_date = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0, tzinfo=tz)
        # Один день в API: оба параметра — дата завтра (Y-m-d совпадает)
        end_date = start_date

        try:
            records = await yclients_client.get_records(
                start_date=start_date,
                end_date=end_date,
            )
            # Если пусто — пробуем диапазон на 2 дня (некоторые версии API ожидают end как следующий день)
            if not records:
                day_after = start_date + timedelta(days=1)
                records = await yclients_client.get_records(
                    start_date=start_date,
                    end_date=day_after,
                )
                if records:
                    filtered = []
                    for r in records:
                        dt_str = r.get("datetime") or ""
                        try:
                            rd = datetime.fromisoformat(
                                dt_str.replace("Z", "+00:00")
                            )
                            if rd.tzinfo:
                                rd = rd.astimezone(tz)
                            if rd.date() == tomorrow:
                                filtered.append(r)
                        except (ValueError, TypeError):
                            continue
                    records = filtered

            logger.info(
                f"Reminder check: tomorrow={tomorrow} tz={settings.REMINDER_TIMEZONE}, "
                f"records_count={len(records)}"
            )

        except Exception as e:
            logger.error(f"Failed to get records from YClients: {str(e)}")
            return

        sent_count = 0
        skipped_count = 0

        for record in records:
            if not isinstance(record, dict):
                continue
            rid = record_id_safe(record)
            cid = record_client_id(record)
            if rid is None or cid is None:
                logger.info(f"Skip record (missing id or client): keys={list(record.keys())[:10]}")
                skipped_count += 1
                continue
            appt_dt = record_appointment_datetime(record)
            if appt_dt is None:
                logger.info(f"Skip record {rid}: no valid datetime")
                skipped_count += 1
                continue

            try:
                async for session in db_manager.get_session():
                    user = await UserCRUD.get_by_yclients_client_id(
                        session=session,
                        yclients_client_id=cid,
                    )

                    if not user:
                        logger.info(
                            f"Skip record {rid}: no bot user for yclients_client_id={cid}"
                        )
                        skipped_count += 1
                        continue

                    existing = await ReminderCRUD.get_by_record_id(
                        session=session,
                        record_id=rid,
                    )

                    if existing and existing.is_sent:
                        skipped_count += 1
                        continue

                    if not existing:
                        reminder = await ReminderCRUD.create(
                            session=session,
                            user_chat_id=user.chat_id,
                            record_id=rid,
                            appointment_datetime=appt_dt,
                            service_name=record_service_name(record),
                            staff_name=record_staff_name(record),
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
                logger.error(f"Error processing record {rid}: {str(e)}", exc_info=True)
                skipped_count += 1

        logger.info(f"Reminder check completed. Sent: {sent_count}, Skipped: {skipped_count}")

    def start(self) -> None:
        """Запуск планировщика: раз в день в REMINDER_CHECK_TIME по REMINDER_TIMEZONE."""
        hour, minute = self._parse_reminder_time()
        try:
            tz = ZoneInfo(settings.REMINDER_TIMEZONE or "UTC")
        except Exception:
            tz = ZoneInfo("UTC")

        # Отдельная async-функция вместо bound method — надёжнее с AsyncIOExecutor
        async def _run() -> None:
            await self.check_and_send_reminders()
            try:
                # Отчёт отправляем в том же ежедневном цикле, чтобы не потерять отдельную джобу.
                target = datetime.now(tz).date() + timedelta(days=1)
                await send_admin_report_for_date(self.bot, target)
            except Exception as e:
                logger.error("Failed to send daily admin report: %s", e, exc_info=True)

        self.scheduler.add_job(
            _run,
            trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
            id="check_reminders",
            replace_existing=True,
            # Если бот был выключен в 10:00 — при следующем старте всё равно выполнить (в течение суток)
            misfire_grace_time=86400,
            coalesce=True,
        )

        self.scheduler.start()
        job = self.scheduler.get_job("check_reminders")
        logger.info(
            f"Scheduler started. Reminders daily at {hour:02d}:{minute:02d} {settings.REMINDER_TIMEZONE}, "
            f"next_run={getattr(job, 'next_run_time', None)}"
        )
        logger.info("Admin report is sent right after daily reminders run")

    def shutdown(self) -> None:
        """Остановка планировщика"""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")