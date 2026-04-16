import logging
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.config import settings
from src.database.crud import NotificationLogCRUD, ReminderCRUD, RescheduleRequestCRUD, UserCRUD
from src.database.database import db_manager
from src.services.yclients import yclients_client
from src.utils.record_helpers import (
    record_appointment_datetime,
    record_client_id,
    record_id as record_id_safe,
    record_staff_name,
)

logger = logging.getLogger(__name__)


def _chunks(text: str, limit: int = 3500) -> list[str]:
    parts: list[str] = []
    buf = ""
    for line in text.splitlines(keepends=True):
        if len(buf) + len(line) > limit and buf:
            parts.append(buf)
            buf = ""
        buf += line
    if buf:
        parts.append(buf)
    return parts


def _format_record_line(
    *,
    appt: datetime,
    patient: str,
    doctor: str,
    status: str,
) -> str:
    return f"- {appt.strftime('%d.%m %H:%M')} · Пациент: {patient} · Доктор: {doctor} · {status}"


async def send_admin_report_for_date(bot: Bot, target: date) -> None:
    """
    Ежедневный отчёт админу:
    - все записи из Dentist plus на target
    - кому отправили/не отправили и почему
    - какой ответ получен (подтвердил/отменил/перенос/нет ответа)
    """
    try:
        tz = ZoneInfo(settings.REMINDER_TIMEZONE or "UTC")
    except Exception:
        tz = ZoneInfo("UTC")

    start = datetime(target.year, target.month, target.day, 0, 0, 0, tzinfo=tz)
    end = start  # API принимает только даты

    records: list[dict[str, Any]] = []
    try:
        records = await yclients_client.get_records(start_date=start, end_date=end)
        if not records:
            # fallback: inclusive/exclusive end_date
            records = await yclients_client.get_records(
                start_date=start,
                end_date=start + timedelta(days=1),
            )
            # оставляем только target
            filtered = []
            for r in records:
                appt = record_appointment_datetime(r) if isinstance(r, dict) else None
                if appt and appt.astimezone(tz).date() == target:
                    filtered.append(r)
            records = filtered
    except Exception as e:
        logger.error("Failed to build admin report (Dentist plus): %s", e, exc_info=True)

    # Подтягиваем пользователей по yclients_client_id (чтобы знать, кто зарегистрирован в боте)
    client_ids: set[int] = set()
    for r in records:
        if not isinstance(r, dict):
            continue
        cid = record_client_id(r)
        if cid is not None:
            client_ids.add(cid)

    users_by_client_id: dict[int, int] = {}  # yclients_client_id -> user_chat_id
    async for session in db_manager.get_session():
        for cid in client_ids:
            user = await UserCRUD.get_by_yclients_client_id(session=session, yclients_client_id=cid)
            if user:
                users_by_client_id[cid] = user.chat_id

    sent = 0
    not_sent = 0
    no_bot = 0
    confirmed = 0
    cancelled = 0
    reschedule = 0

    lines: list[str] = []
    async for session in db_manager.get_session():
        for r in records:
            if not isinstance(r, dict):
                continue

            rid = record_id_safe(r)
            cid = record_client_id(r)
            appt = record_appointment_datetime(r)
            if rid is None or cid is None or appt is None:
                continue

            appt_local = appt.astimezone(tz)
            if appt_local.date() != target:
                continue

            doctor = record_staff_name(r)
            patient_name = ""
            client = r.get("client") if isinstance(r.get("client"), dict) else {}
            if isinstance(client, dict):
                patient_name = str(client.get("name") or "").strip()
            if not patient_name:
                patient_name = f"#{cid}"

            user_chat_id = users_by_client_id.get(cid)
            if not user_chat_id:
                no_bot += 1
                lines.append(
                    _format_record_line(
                        appt=appt_local,
                        patient=patient_name,
                        doctor=doctor,
                        status="не зарегистрирован в боте",
                    )
                )
                continue

            reminder = await ReminderCRUD.get_by_record_id(session=session, record_id=rid)
            if not reminder:
                not_sent += 1
                lines.append(
                    _format_record_line(
                        appt=appt_local,
                        patient=patient_name,
                        doctor=doctor,
                        status="нет записи reminder в БД (не отправлено)",
                    )
                )
                continue

            # Ответ пациента
            answer = "⌛ ответа нет"
            if reminder.is_confirmed:
                answer = "✅ подтверждено"
                confirmed += 1
            elif reminder.is_cancelled:
                answer = "❌ отменено"
                cancelled += 1
            else:
                req = await RescheduleRequestCRUD.get_latest_by_record_id(
                    session=session,
                    record_id=rid,
                )
                if req and req.status == "pending":
                    answer = "🔄 запрос на перенос"
                    reschedule += 1

            # Отправка
            if reminder.is_sent:
                sent += 1
                lines.append(
                    _format_record_line(
                        appt=appt_local,
                        patient=patient_name,
                        doctor=doctor,
                        status=f"отправлено · {answer}",
                    )
                )
                continue

            not_sent += 1
            last_log = await NotificationLogCRUD.get_latest_by_record_and_type(
                session=session,
                record_id=rid,
                message_type="reminder",
            )
            if last_log and not last_log.is_successful:
                err = (last_log.error_message or "ошибка").strip()
                lines.append(
                    _format_record_line(
                        appt=appt_local,
                        patient=patient_name,
                        doctor=doctor,
                        status=f"НЕ отправлено · ошибка: {err} · {answer}",
                    )
                )
            else:
                lines.append(
                    _format_record_line(
                        appt=appt_local,
                        patient=patient_name,
                        doctor=doctor,
                        status=f"НЕ отправлено · {answer}",
                    )
                )

    header = (
        f"📋 Отчёт по напоминаниям на {target.strftime('%d.%m.%Y')}\n"
        f"- Всего записей в Dentist plus: {len(records)}\n"
        f"- Не зарегистрированы в боте: {no_bot}\n"
        f"- Отправлено: {sent}\n"
        f"- Не отправлено: {not_sent}\n"
        f"- Ответы: ✅ {confirmed} / ❌ {cancelled} / 🔄 {reschedule}\n\n"
    )

    body = "\n".join(lines) if lines else "Нет записей."
    text = header + body

    for part in _chunks(text):
        try:
            await bot.send_message(chat_id=settings.ADMIN_CHAT_ID, text=part)
        except TelegramForbiddenError:
            logger.error(
                "Cannot deliver admin report: admin blocked bot or never started chat. admin_id=%s",
                settings.ADMIN_CHAT_ID,
            )
            return
        except TelegramBadRequest as e:
            logger.error(
                "Cannot deliver admin report (bad request). admin_id=%s error=%s",
                settings.ADMIN_CHAT_ID,
                e,
            )
            return

