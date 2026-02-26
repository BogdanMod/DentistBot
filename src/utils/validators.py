"""Валидация данных"""
import re
from typing import Optional

import phonenumbers
from phonenumbers import NumberParseException


def validate_international_phone(phone: str, default_region: str = "RU") -> Optional[str]:
    """
    Точная валидация международного номера через phonenumbers.

    Возвращает номер в формате E.164 (например, +79001234567),
    или None, если номер невалидный.
    """
    try:
        parsed_number = phonenumbers.parse(phone, default_region)
    except NumberParseException:
        return None

    if not phonenumbers.is_valid_number(parsed_number):
        return None

    return phonenumbers.format_number(
        parsed_number,
        phonenumbers.PhoneNumberFormat.E164,
    )


def validate_phone(phone: str) -> Optional[str]:
    """
    Валидация и нормализация номера телефона

    Принимает форматы:
    - +79001234567
    - 89001234567
    - 8 (900) 123-45-67
    - +7 900 123 45 67

    Возвращает в формате: +79001234567 или None если невалидный
    """
    normalized_phone = validate_international_phone(phone)
    if normalized_phone:
        return normalized_phone

    # Fallback на старую логику для случаев, когда номер вводят в нестандартном виде.
    cleaned = re.sub(r'[^\d+]', '', phone)
    if cleaned.startswith('+'):
        cleaned = cleaned[1:]
    if cleaned.startswith('8') and len(cleaned) == 11:
        cleaned = '7' + cleaned[1:]
    if len(cleaned) == 11 and cleaned.startswith('7'):
        return '+' + cleaned
    return None


def validate_email(email: str) -> Optional[str]:
    """Простая валидация email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(pattern, email):
        return email.lower()
    return None
