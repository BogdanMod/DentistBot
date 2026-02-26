"""Inline клавиатуры"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def create_reminder_keyboard(record_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для напоминания о записи"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="✅ Подтвердить",
                callback_data=f"confirm_{record_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔄 Перенести",
                callback_data=f"reschedule_{record_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="❌ Отменить",
                callback_data=f"cancel_{record_id}",
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def create_cancel_reason_keyboard(record_id: int) -> InlineKeyboardMarkup:
    """Клавиатура с причинами отмены"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="🤒 Плохое самочувствие",
                callback_data=f"cancel_reason_{record_id}_ill",
            ),
        ],
        [
            InlineKeyboardButton(
                text="⏰ Занят/Занята",
                callback_data=f"cancel_reason_{record_id}_busy",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📝 Другая причина",
                callback_data=f"cancel_reason_{record_id}_other",
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)