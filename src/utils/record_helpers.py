"""Безопасное извлечение полей из записи YClients (без KeyError)."""
from datetime import datetime, timezone
from typing import Any, Optional


def record_client_id(record: dict[str, Any]) -> Optional[int]:
    client = record.get("client")
    if not client or not isinstance(client, dict):
        return None
    cid = client.get("id")
    if cid is None:
        return None
    try:
        return int(cid)
    except (TypeError, ValueError):
        return None


def record_id(record: dict[str, Any]) -> Optional[int]:
    rid = record.get("id")
    if rid is None:
        return None
    try:
        return int(rid)
    except (TypeError, ValueError):
        return None


def record_service_name(record: dict[str, Any]) -> str:
    services = record.get("services") or []
    if not services:
        return "Услуга"
    first = services[0]
    if isinstance(first, dict):
        return str(first.get("title") or first.get("name") or "Услуга")
    return "Услуга"


def record_staff_name(record: dict[str, Any]) -> str:
    staff = record.get("staff")
    if not staff or not isinstance(staff, dict):
        return "Доктор"
    name = str(staff.get("name") or "Доктор")
    if name.strip().lower() == "мастер":
        return "Доктор"
    return name


def record_appointment_datetime(record: dict[str, Any]) -> Optional[datetime]:
    dt_str = record.get("datetime")
    if not dt_str or not isinstance(dt_str, str):
        return None
    try:
        s = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc).astimezone()
        return dt
    except (ValueError, TypeError):
        return None
