"""Обработчики команд и основного меню"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from src.config import settings
from src.database.crud import UserCRUD
from src.database.database import db_manager
from src.services.admin_report import send_admin_report_for_date
from src.services.yclients import yclients_client
from src.utils.validators import validate_phone

logger = logging.getLogger(__name__)
commands_router = Router()


class ConsultationStates(StatesGroup):
    waiting_name = State()
    waiting_phone = State()


_incomplete_booking_tasks: dict[int, asyncio.Task] = {}
MAIN_MENU_BUTTONS = {
    "📅 Записаться на консультацию",
    "📆 Мои записи",
    "🦷 Стоимость лечения",
    "📸 Кейсы ДО / ПОСЛЕ",
    "👩🏻‍⚕️ Наши врачи",
    "🔎 Какая у меня проблема?",
    "ℹ️ Как проходит лечение",
    "❓ Частые вопросы",
    "📍 Контакты",
}


def _is_contacts_button(text: str) -> bool:
    return "контакт" in text.lower()


MAIN_MENU_TEXT = (
    "✨ Здравствуйте!\n\n"
    "Это официальный бот команды доктора Шевцовой 🦷\n\n"
    "Здесь вы можете:\n"
    "• 📅 записаться на консультацию\n"
    "• 📆 посмотреть дату запланированного визита\n"
    "• 🦷 узнать стоимость лечения\n"
    "• 👩🏻‍⚕️ познакомиться с врачами\n"
    "• 📸 посмотреть результаты лечения\n"
    "• ❓ задать вопрос\n\n"
    "Выберите нужный раздел ⬇️"
)


def _main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Записаться на консультацию"), KeyboardButton(text="📆 Мои записи")],
            [KeyboardButton(text="🦷 Стоимость лечения"), KeyboardButton(text="📸 Кейсы ДО / ПОСЛЕ")],
            [KeyboardButton(text="👩🏻‍⚕️ Наши врачи"), KeyboardButton(text="🔎 Какая у меня проблема?")],
            [KeyboardButton(text="ℹ️ Как проходит лечение"), KeyboardButton(text="❓ Частые вопросы")],
            [KeyboardButton(text="📍 Контакты")],
        ],
        resize_keyboard=True,
    )


def _book_specialist_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Ортодонт-гнатолог", callback_data="book_spec_ortho_gnato")],
            [InlineKeyboardButton(text="Терапевт", callback_data="book_spec_therapist")],
            [InlineKeyboardButton(text="Хирург", callback_data="book_spec_surgeon")],
            [InlineKeyboardButton(text="Ортопед", callback_data="book_spec_orthopedist")],
            [InlineKeyboardButton(text="Профессиональная гигиена", callback_data="book_spec_hygiene")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
        ]
    )


def _cost_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Ортодонтическое (брекеты/элайнеры)", callback_data="cost_orthodontic")],
            [InlineKeyboardButton(text="Гнатологическое (лечение сустава)", callback_data="cost_gnathology")],
            [InlineKeyboardButton(text="Имплантация", callback_data="cost_implant")],
            [InlineKeyboardButton(text="Ортопедия (виниры/коронки)", callback_data="cost_orthopedics")],
            [InlineKeyboardButton(text="Лечение зубов", callback_data="cost_therapy")],
            [InlineKeyboardButton(text="Профессиональная гигиена", callback_data="cost_hygiene")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
        ]
    )


def _book_and_cases_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Записаться на консультацию", callback_data="go_booking")],
            [InlineKeyboardButton(text="📸 Посмотреть кейсы", callback_data="go_cases")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_cost_menu")],
        ]
    )


def _cases_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Скученность зубов", callback_data="case_crowding")],
            [InlineKeyboardButton(text="Неровные зубы", callback_data="case_crooked")],
            [InlineKeyboardButton(text="Щели между зубами", callback_data="case_gaps")],
            [InlineKeyboardButton(text="Неправильный прикус", callback_data="case_bite")],
            [InlineKeyboardButton(text="Потеря зуба", callback_data="case_missing")],
            [InlineKeyboardButton(text="Эстетика улыбки", callback_data="case_smile")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
        ]
    )


def _book_only_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Записаться на консультацию", callback_data="go_booking")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
        ]
    )


def _doctors_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Ортодонт-гнатолог", callback_data="doc_ortho_gnato")],
            [InlineKeyboardButton(text="Ортодонт-гигиенист", callback_data="doc_ortho_hygienist")],
            [InlineKeyboardButton(text="Терапевт", callback_data="doc_therapist")],
            [InlineKeyboardButton(text="Хирург", callback_data="doc_surgeon")],
            [InlineKeyboardButton(text="Ортопед", callback_data="doc_orthopedist")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
        ]
    )


def _doctor_actions_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Работы врача", callback_data="go_cases")],
            [InlineKeyboardButton(text="Записаться на консультацию", callback_data="go_booking")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_doctors_menu")],
        ]
    )


def _diagnostics_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Неровные зубы", callback_data="diag_ortho")],
            [InlineKeyboardButton(text="Боль в зубе", callback_data="diag_therapist")],
            [InlineKeyboardButton(text="Щелкает или болит челюсть", callback_data="diag_gnato")],
            [InlineKeyboardButton(text="Отсутствует зуб", callback_data="diag_orthopedist")],
            [InlineKeyboardButton(text="Хочу улучшить эстетику улыбки", callback_data="diag_esthetic")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
        ]
    )


def _faq_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Больно ли ставить брекеты?", callback_data="faq_braces_hurt")],
            [InlineKeyboardButton(text="Сколько длится ортодонтическое лечение?", callback_data="faq_ortho_time")],
            [InlineKeyboardButton(text="Можно ли лечить зубы взрослым?", callback_data="faq_adults")],
            [InlineKeyboardButton(text="Как проходит имплантация?", callback_data="faq_implant")],
            [InlineKeyboardButton(text="Как часто делать профессиональную гигиену?", callback_data="faq_hygiene")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
        ]
    )


def _contacts_kb() -> InlineKeyboardMarkup:
    tg = settings.CLINIC_TELEGRAM.strip()
    tg_url = f"https://t.me/{tg[1:]}" if tg.startswith("@") else "https://t.me/"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📍 Построить маршрут", url=settings.CLINIC_MAP_URL)],
            [InlineKeyboardButton(text="📞 Позвонить", url=f"tel:{settings.CLINIC_PHONE}")],
            [InlineKeyboardButton(text="💬 Написать администратору", url=tg_url)],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
        ]
    )


def _normalize_phone(raw: str) -> Optional[str]:
    return validate_phone(raw)


async def _handle_menu_shortcut_in_fsm(message: Message, state: FSMContext) -> bool:
    text = (message.text or "").strip()
    if text not in MAIN_MENU_BUTTONS and not _is_contacts_button(text):
        return False

    await state.clear()
    _cancel_incomplete_booking_reminder(message.from_user.id)

    if _is_contacts_button(text):
        await message.answer(
            "Мы будем рады видеть Вас на консультации.\n"
            f"Адрес: {settings.CLINIC_ADDRESS}\n"
            f"Телефон: {settings.CLINIC_PHONE}\n"
            f"Telegram: {settings.CLINIC_TELEGRAM}",
            reply_markup=_contacts_kb(),
        )
        return True

    await message.answer(
        "Вернул вас в главное меню. Выберите нужный раздел ⬇️",
        reply_markup=_main_menu_kb(),
    )
    return True


async def _schedule_incomplete_booking_reminder(bot, chat_id: int) -> None:
    await asyncio.sleep(6 * 60 * 60)
    await bot.send_message(
        chat_id=chat_id,
        text=(
            "Вы начали запись на консультацию.\n"
            "Хотите подобрать удобное время?"
        ),
        reply_markup=_book_only_kb(),
    )


def _restart_incomplete_booking_reminder(bot, chat_id: int) -> None:
    task = _incomplete_booking_tasks.get(chat_id)
    if task and not task.done():
        task.cancel()
    _incomplete_booking_tasks[chat_id] = asyncio.create_task(
        _schedule_incomplete_booking_reminder(bot, chat_id)
    )


def _cancel_incomplete_booking_reminder(chat_id: int) -> None:
    task = _incomplete_booking_tasks.pop(chat_id, None)
    if task and not task.done():
        task.cancel()


@commands_router.message(CommandStart())
async def start_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(MAIN_MENU_TEXT, reply_markup=_main_menu_kb())


@commands_router.message(F.text == "📅 Записаться на консультацию")
async def consultation_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    _restart_incomplete_booking_reminder(message.bot, message.from_user.id)
    await message.answer(
        "Выберите специалиста для консультации.",
        reply_markup=_book_specialist_kb(),
    )


@commands_router.callback_query(F.data == "go_booking")
async def consultation_start_callback(callback, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    _restart_incomplete_booking_reminder(callback.bot, callback.from_user.id)
    await callback.message.answer(
        "Выберите специалиста для консультации.",
        reply_markup=_book_specialist_kb(),
    )


@commands_router.callback_query(F.data.startswith("book_spec_"))
async def consultation_choose_specialist(callback, state: FSMContext) -> None:
    await callback.answer()
    specialist_map = {
        "book_spec_ortho_gnato": "Ортодонт-гнатолог",
        "book_spec_therapist": "Терапевт",
        "book_spec_surgeon": "Хирург",
        "book_spec_orthopedist": "Ортопед",
        "book_spec_hygiene": "Профессиональная гигиена",
    }
    specialist = specialist_map.get(callback.data)
    if not specialist:
        return
    await state.set_state(ConsultationStates.waiting_name)
    await state.update_data(specialist=specialist)
    _restart_incomplete_booking_reminder(callback.bot, callback.from_user.id)
    await callback.message.answer("Как вас зовут? ФИО")


@commands_router.message(ConsultationStates.waiting_name)
async def consultation_get_name(message: Message, state: FSMContext) -> None:
    if await _handle_menu_shortcut_in_fsm(message, state):
        return
    full_name = (message.text or "").strip()
    if len(full_name) < 2:
        await message.answer("Пожалуйста, укажите корректное ФИО.")
        return
    await state.update_data(full_name=full_name)
    await state.set_state(ConsultationStates.waiting_phone)
    _restart_incomplete_booking_reminder(message.bot, message.from_user.id)
    await message.answer("Оставьте номер телефона.")


@commands_router.message(ConsultationStates.waiting_phone)
async def consultation_get_phone(message: Message, state: FSMContext) -> None:
    if await _handle_menu_shortcut_in_fsm(message, state):
        return
    normalized = _normalize_phone(message.text or "")
    if not normalized:
        await message.answer("Введите корректный номер телефона в формате +7XXXXXXXXXX.")
        return

    data = await state.get_data()
    specialist = data.get("specialist", "Не указан")
    full_name = data.get("full_name", "Не указано")

    admin_message = (
        "🆕 Новая заявка на консультацию\n\n"
        f"👤 Пациент: {full_name}\n"
        f"📞 Телефон: {normalized}\n"
        f"🩺 Специалист: {specialist}\n"
        f"🕒 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    try:
        await message.bot.send_message(settings.ADMIN_CHAT_ID, admin_message)
    except Exception as e:
        logger.error("Failed to send consultation lead to admin: %s", e)

    _cancel_incomplete_booking_reminder(message.from_user.id)
    await state.clear()
    await message.answer(
        "Спасибо!\n"
        "Администратор свяжется с Вами для подтверждения записи."
    )
    await message.answer(
        "Полезная информация перед приёмом:\n"
        f"📍 Адрес клиники: {settings.CLINIC_ADDRESS}\n"
        "🪥 Как подготовиться: за 2 часа не употребляйте красящие напитки и возьмите список жалоб.\n"
        "🧾 Что взять с собой: паспорт и, при наличии, предыдущие снимки/заключения."
    )


@commands_router.message(F.text == "📆 Мои записи")
async def my_records(message: Message) -> None:
    async for session in db_manager.get_session():
        user = await UserCRUD.get_by_chat_id(session, message.from_user.id)
    if not user or not user.yclients_client_id:
        await message.answer(
            "Пока не удалось найти ваши записи в системе.\n"
            "Нажмите «📅 Записаться на консультацию», и администратор поможет."
        )
        return
    try:
        tz = ZoneInfo(settings.REMINDER_TIMEZONE or "UTC")
    except Exception:
        tz = ZoneInfo("UTC")
    now = datetime.now(tz)
    records = await yclients_client.get_records(
        start_date=now,
        end_date=now + timedelta(days=180),
        client_id=user.yclients_client_id,
    )
    upcoming: list[str] = []
    for record in records:
        dt_raw = record.get("datetime")
        if not isinstance(dt_raw, str):
            continue
        try:
            dt = datetime.fromisoformat(dt_raw.replace("Z", "+00:00")).astimezone(tz)
        except ValueError:
            continue
        if dt < now:
            continue
        doctor = (record.get("staff") or {}).get("name", "Доктор")
        upcoming.append(f"• {dt.strftime('%d.%m.%Y %H:%M')} — {doctor}")
    if not upcoming:
        await message.answer("Ближайших записей не найдено.")
        return
    await message.answer("Ваши ближайшие записи:\n" + "\n".join(upcoming[:5]))


@commands_router.message(F.text == "🦷 Стоимость лечения")
async def cost_start(message: Message) -> None:
    await message.answer("Выберите интересующее лечение.", reply_markup=_cost_menu_kb())


@commands_router.callback_query(F.data.startswith("cost_"))
async def cost_item(callback) -> None:
    await callback.answer()
    pricing = {
        "cost_orthodontic": (
            "Ортодонтическое",
            "• Консультация ортодонта-гнатолога — 6.000₽\n"
            "• Диагностика — 31.250₽\n"
            "• Средний диапазон фиксации брекет-системы — 260.000₽-285.000₽\n"
            "• Ежемесячная коррекция брекет-системы — 8.750₽-12.500₽\n"
            "• Лечение на элайнерах (под ключ) — 237.000₽-587.000₽"
        ),
        "cost_gnathology": (
            "Гнатологическое",
            "• Лечение сустава (сплинт-терапия) — 125.000₽-162.500₽ (под ключ)"
        ),
        "cost_implant": (
            "Имплантация",
            "• Раздел в заполнении — пока пусто."
        ),
        "cost_orthopedics": (
            "Ортопедия",
            "• Первичная консультация — 1.900₽\n"
            "• Консультация по направлению от другого доктора внутри команды — бесплатно\n"
            "• Одиночная реставрация с опорой на зуб (керамика/циркон) — 75.000₽\n"
            "• Одиночная реставрация на имплантате (керамика/циркон) — 81.250₽\n"
            "• Ультратонкий винир — 87.500₽\n"
            "• Временная коронка (на своем зубе) — 15.000₽\n"
            "• Временная коронка на имплантате — 22.500₽\n"
            "• Временная лабораторная реставрация (пластмасса/фрезерованный композит) — 15.000₽\n"
            "• Временная реставрация, изготовленная в клинике — пока пусто"
        ),
        "cost_therapy": (
            "Лечение зубов",
            "• Первичная консультация — 1.900₽\n"
            "• Консультация по направлению от другого доктора внутри команды — бесплатно\n"
            "• Лечение кариеса под микроскопом — 10.000₽-21.500₽\n"
            "• Лечение каналов под микроскопом — 40.000₽-57.500₽\n"
            "• Перелечивание каналов — 48.000₽-82.500₽\n"
            "• Эстетическая реставрация — 21.000₽-31.500₽\n"
            "• Профессиональная гигиена полости рта — 11.250₽\n"
            "• Профессиональная гигиена полости рта при регулярных посещениях — 10.000₽"
        ),
        "cost_hygiene": (
            "Профессиональная гигиена",
            "• Профессиональная гигиена полости рта — 11.250₽\n"
            "• Профессиональная гигиена полости рта при регулярных посещениях — 10.000₽\n"
            "• Профессиональная гигиена полости рта (с брекет-системой) — 14.375₽"
        ),
        # Совместимость со старыми callback_data, если нажимают старые сообщения
        "cost_ortho": (
            "Ортодонтическое",
            "• Консультация ортодонта-гнатолога — 6.000₽\n"
            "• Диагностика — 31.250₽\n"
            "• Средний диапазон фиксации брекет-системы — 260.000₽-285.000₽\n"
            "• Ежемесячная коррекция брекет-системы — 8.750₽-12.500₽\n"
            "• Лечение на элайнерах (под ключ) — 237.000₽-587.000₽"
        ),
        "cost_aligners": (
            "Ортодонтическое",
            "• Консультация ортодонта-гнатолога — 6.000₽\n"
            "• Диагностика — 31.250₽\n"
            "• Лечение на элайнерах (под ключ) — 237.000₽-587.000₽"
        ),
        "cost_braces": (
            "Ортодонтическое",
            "• Средний диапазон фиксации брекет-системы — 260.000₽-285.000₽\n"
            "• Ежемесячная коррекция брекет-системы — 8.750₽-12.500₽"
        ),
        "cost_veneers": (
            "Ортопедия",
            "• Первичная консультация — 1.900₽\n"
            "• Консультация по направлению от другого доктора внутри команды — бесплатно\n"
            "• Одиночная реставрация с опорой на зуб (керамика/циркон) — 75.000₽\n"
            "• Одиночная реставрация на имплантате (керамика/циркон) — 81.250₽\n"
            "• Ультратонкий винир — 87.500₽\n"
            "• Временная коронка (на своем зубе) — 15.000₽\n"
            "• Временная коронка на имплантате — 22.500₽"
        ),
    }
    title, price = pricing.get(callback.data, ("Лечение", "Стоимость уточняется"))
    await callback.message.answer(
        f"{title}\n"
        f"{price}\n\n"
        "Точная стоимость определяется после диагностики и составления индивидуального плана лечения.",
        reply_markup=_book_and_cases_kb(),
    )


@commands_router.callback_query(F.data == "go_cases")
async def go_cases(callback) -> None:
    await callback.answer()
    await callback.message.answer("Выберите проблему.", reply_markup=_cases_menu_kb())


@commands_router.callback_query(F.data == "back_main")
async def back_main(callback) -> None:
    await callback.answer()
    await callback.message.answer(
        "Главное меню ⬇️",
        reply_markup=_main_menu_kb(),
    )


@commands_router.callback_query(F.data == "back_cost_menu")
async def back_cost_menu(callback) -> None:
    await callback.answer()
    await callback.message.answer("Выберите интересующее лечение.", reply_markup=_cost_menu_kb())


@commands_router.callback_query(F.data == "back_doctors_menu")
async def back_doctors_menu(callback) -> None:
    await callback.answer()
    await callback.message.answer(
        "Наша команда специалистов работает комплексно, чтобы обеспечить максимально качественный результат лечения.",
        reply_markup=_doctors_menu_kb(),
    )


@commands_router.message(F.text == "📸 Кейсы ДО / ПОСЛЕ")
async def cases_start(message: Message) -> None:
    await message.answer("Выберите проблему.", reply_markup=_cases_menu_kb())


@commands_router.callback_query(F.data.startswith("case_"))
async def case_item(callback) -> None:
    await callback.answer()
    problem_map = {
        "case_crowding": "скученность зубов",
        "case_crooked": "неровные зубы",
        "case_gaps": "щели между зубами",
        "case_bite": "неправильный прикус",
        "case_missing": "потеря зуба",
        "case_smile": "эстетика улыбки",
    }
    problem = problem_map.get(callback.data, "проблема")
    await callback.message.answer(
        "Фото ДО\n"
        "Фото ПОСЛЕ\n\n"
        "Описание:\n"
        "Пациент: 27 лет\n"
        f"Жалоба: {problem}\n"
        "Лечение: ортодонтическое лечение\n"
        "Срок: 14 месяцев",
        reply_markup=_book_only_kb(),
    )


@commands_router.message(F.text == "👩🏻‍⚕️ Наши врачи")
async def doctors_start(message: Message) -> None:
    await message.answer(
        "Наша команда специалистов работает комплексно, чтобы обеспечить "
        "максимально качественный результат лечения.",
        reply_markup=_doctors_menu_kb(),
    )


@commands_router.callback_query(F.data.startswith("doc_"))
async def doctor_item(callback) -> None:
    await callback.answer()
    doctor_map = {
        "doc_ortho_gnato": ("Иванова Анна Сергеевна", "Ортодонт-гнатолог"),
        "doc_ortho_hygienist": ("Петрова Мария Олеговна", "Ортодонт-гигиенист"),
        "doc_therapist": ("Смирнов Алексей Викторович", "Терапевт"),
        "doc_surgeon": ("Кузнецов Дмитрий Павлович", "Хирург"),
        "doc_orthopedist": ("Соколова Елена Игоревна", "Ортопед"),
    }
    name, spec = doctor_map.get(callback.data, ("Врач", "Специалист"))
    await callback.message.answer(
        "Фото врача\n"
        f"{name}\n"
        f"{spec}\n\n"
        "Краткое описание:\n"
        "• опыт работы: 10+ лет\n"
        "• ключевые направления: комплексное лечение\n"
        "• подход: персональный план и бережная коммуникация\n\n"
        "Видео от врача (30–40 сек):\n"
        "чем занимается и какой подход к лечению.",
        reply_markup=_doctor_actions_kb(),
    )


@commands_router.message(F.text == "🔎 Какая у меня проблема?")
async def mini_diag_start(message: Message) -> None:
    await message.answer(
        "Ответьте на несколько вопросов, и мы подскажем, к какому специалисту лучше обратиться.\n\n"
        "Что вас беспокоит?",
        reply_markup=_diagnostics_menu_kb(),
    )


@commands_router.callback_query(F.data.startswith("diag_"))
async def mini_diag_result(callback) -> None:
    await callback.answer()
    map_result = {
        "diag_ortho": "ортодонта",
        "diag_therapist": "терапевта",
        "diag_gnato": "ортодонта-гнатолога",
        "diag_orthopedist": "ортопеда",
        "diag_esthetic": "ортодонта/ортопеда",
    }
    spec = map_result.get(callback.data, "специалиста")
    await callback.message.answer(
        f"Вам может подойти консультация: {spec}.",
        reply_markup=_book_only_kb(),
    )


@commands_router.message(F.text == "ℹ️ Как проходит лечение")
async def treatment_flow(message: Message) -> None:
    await message.answer(
        "Лечение проходит в несколько этапов.\n\n"
        "Этап 1. Первичная консультация\n"
        "Осмотр, обсуждение жалоб, рекомендации.\n\n"
        "Этап 2. Диагностика\n"
        "Снимки, сканирование зубов, анализ прикуса.\n\n"
        "Этап 3. План лечения\n"
        "Врач составляет индивидуальный план.\n\n"
        "Этап 4. Основное лечение\n"
        "Проведение всех необходимых процедур.\n\n"
        "Этап 5. Контроль и поддержка результата.",
        reply_markup=_book_only_kb(),
    )


@commands_router.message(F.text == "❓ Частые вопросы")
async def faq_start(message: Message) -> None:
    await message.answer("Выберите интересующий вопрос.", reply_markup=_faq_menu_kb())


@commands_router.callback_query(F.data.startswith("faq_"))
async def faq_item(callback) -> None:
    await callback.answer()
    answers = {
        "faq_braces_hurt": "В первые 3–7 дней возможен дискомфорт, это нормально. Врач даст рекомендации по адаптации.",
        "faq_ortho_time": "В среднем 12–24 месяца, точный срок зависит от клинической ситуации.",
        "faq_adults": "Да, лечить зубы взрослым можно и нужно. Современные методики подходят для любого возраста.",
        "faq_implant": "Имплантация проходит поэтапно: диагностика, установка импланта, приживление, протезирование.",
        "faq_hygiene": "Обычно каждые 6 месяцев, при ортодонтическом лечении — чаще по рекомендации врача.",
    }
    await callback.message.answer(answers.get(callback.data, "Ответ уточняется у врача."), reply_markup=_book_only_kb())


@commands_router.message(F.text.func(lambda t: isinstance(t, str) and "контакт" in t.lower()))
async def contacts(message: Message) -> None:
    await message.answer(
        "Мы будем рады видеть Вас на консультации.\n"
        f"Адрес: {settings.CLINIC_ADDRESS}\n"
        f"Телефон: {settings.CLINIC_PHONE}\n"
        f"Telegram: {settings.CLINIC_TELEGRAM}",
        reply_markup=_contacts_kb(),
    )


@commands_router.message(F.text.startswith("/report"))
async def report_command(message: Message) -> None:
    """Админ-команда отчёта: /report [tomorrow|today|YYYY-MM-DD]"""
    if message.from_user.id != settings.ADMIN_CHAT_ID:
        return

    raw = (message.text or "").strip()
    parts = raw.split(maxsplit=1)
    arg = parts[1].strip() if len(parts) > 1 else "tomorrow"

    try:
        tz = ZoneInfo(settings.REMINDER_TIMEZONE or "UTC")
    except Exception:
        tz = ZoneInfo("UTC")

    today = datetime.now(tz).date()
    target: date
    if arg.lower() in {"tomorrow", "завтра"}:
        target = today + timedelta(days=1)
    elif arg.lower() in {"today", "сегодня"}:
        target = today
    else:
        try:
            target = date.fromisoformat(arg)
        except ValueError:
            await message.answer("Формат: /report tomorrow | today | YYYY-MM-DD")
            return

    await message.answer(f"Готовлю отчёт на {target.strftime('%d.%m.%Y')}…")
    await send_admin_report_for_date(message.bot, target)
