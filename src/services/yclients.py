import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import aiohttp
from aiohttp import ClientError, ClientTimeout

from src.config import settings

logger = logging.getLogger(__name__)


class YClientsAPIError(Exception):
    """Совместимое имя исключения для интеграционного слоя."""


class YClientsRateLimitError(YClientsAPIError):
    """Ошибка превышения лимита запросов."""


def _full_name(user: dict[str, Any]) -> str:
    return " ".join(
        str(user.get(k, "")).strip()
        for k in ("lname", "fname", "mname")
        if str(user.get(k, "")).strip()
    ).strip()


def _to_iso_utc(dt_str: str) -> str:
    parsed = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    try:
        clinic_tz = ZoneInfo(settings.REMINDER_TIMEZONE or "UTC")
    except Exception:
        clinic_tz = ZoneInfo("UTC")
    return parsed.replace(tzinfo=clinic_tz).astimezone(timezone.utc).isoformat()


class YClientsClient:
    """
    Адаптер на Dentist Plus API.
    Оставлен с прежним именем, чтобы минимально затрагивать остальной код.
    """

    def __init__(self):
        self.base_url = settings.DENTIST_PLUS_API_URL.rstrip("/")
        self.login = settings.DENTIST_PLUS_LOGIN
        self.password = settings.DENTIST_PLUS_PASSWORD
        self.branch_id = settings.DENTIST_PLUS_BRANCH_ID

        self.timeout = ClientTimeout(total=30)
        self._session: Optional[aiohttp.ClientSession] = None
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

        self._request_times: list[datetime] = []
        self._max_requests_per_minute = 60

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _check_rate_limit(self) -> None:
        now = datetime.now()
        self._request_times = [t for t in self._request_times if now - t < timedelta(minutes=1)]
        if len(self._request_times) >= self._max_requests_per_minute:
            wait_time = 60 - (now - self._request_times[0]).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                self._request_times.clear()
        self._request_times.append(now)

    async def _auth(self) -> None:
        if not self.login or not self.password:
            raise YClientsAPIError("Dentist Plus credentials are not configured")

        session = await self._get_session()
        url = f"{self.base_url}/auth"
        async with session.post(url, json={"login": self.login, "pass": self.password}) as response:
            data = await response.json()
            if response.status >= 400:
                raise YClientsAPIError(f"Dentist Plus auth failed: {data}")

        self._token = data.get("token")
        expires_at_raw = data.get("expires_at")
        if not self._token:
            raise YClientsAPIError("Dentist Plus auth token missing")

        if isinstance(expires_at_raw, str):
            self._token_expires_at = datetime.fromisoformat(expires_at_raw.replace("Z", "+00:00"))
        else:
            self._token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

    async def _ensure_token(self) -> None:
        now = datetime.now(timezone.utc)
        if not self._token or not self._token_expires_at or now >= (self._token_expires_at - timedelta(minutes=1)):
            await self._auth()

    async def _make_request(self, method: str, endpoint: str, *, auth: bool = True, **kwargs) -> Any:
        await self._check_rate_limit()
        if auth:
            await self._ensure_token()

        session = await self._get_session()
        url = f"{self.base_url}{endpoint if endpoint.startswith('/') else '/' + endpoint}"
        headers = kwargs.pop("headers", {})
        if auth and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"

        for attempt in range(1, 4):
            try:
                async with session.request(method, url, headers=headers, **kwargs) as response:
                    try:
                        data = await response.json()
                    except Exception:
                        text = await response.text()
                        raise YClientsAPIError(f"Dentist Plus non-JSON response: {response.status} {text[:400]}")

                    # Протух токен — один раз пробуем переавторизоваться
                    if response.status == 401 and auth and attempt == 1:
                        self._token = None
                        self._token_expires_at = None
                        await self._ensure_token()
                        continue

                    if response.status >= 400:
                        raise YClientsAPIError(f"Dentist Plus API error: {response.status} {data}")
                    return data
            except ClientError as e:
                if attempt < 3:
                    await asyncio.sleep(1)
                    continue
                raise YClientsAPIError(f"Connection error: {e}")

    async def _collect_paginated(
        self,
        endpoint: str,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        page = 1
        result: list[dict[str, Any]] = []
        while True:
            query = dict(params)
            query["page"] = page
            query.setdefault("per_page", 200)
            payload = await self._make_request("GET", endpoint, params=query)
            data = payload.get("data", []) if isinstance(payload, dict) else []
            meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
            if isinstance(data, list):
                result.extend(data)
            last_page = int(meta.get("last_page") or page)
            if page >= last_page:
                break
            page += 1
        return result

    async def get_records(
        self,
        start_date: datetime,
        end_date: datetime,
        client_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "date_from": start_date.strftime("%Y-%m-%d"),
            "date_to": end_date.strftime("%Y-%m-%d"),
            "branch_id": self.branch_id,
            "with_deleted": "1",
        }
        if client_id:
            params["patient_id"] = client_id

        try:
            visits = await self._collect_paginated("/visits", params)
        except YClientsAPIError as e:
            logger.error("Failed to get visits: %s", e)
            return []

        # Нормализуем в старый формат для текущего кода
        records: list[dict[str, Any]] = []
        for v in visits:
            if not isinstance(v, dict):
                continue
            patient = v.get("patient") if isinstance(v.get("patient"), dict) else {}
            doctor = v.get("doctor") if isinstance(v.get("doctor"), dict) else {}
            start = v.get("start")
            if not isinstance(start, str):
                continue
            try:
                dt_iso = _to_iso_utc(start)
            except ValueError:
                continue

            records.append(
                {
                    "id": v.get("id"),
                    "datetime": dt_iso,
                    "client": {
                        "id": patient.get("id"),
                        "name": _full_name(patient),
                        "phone": patient.get("phone", ""),
                    },
                    "staff": {
                        "id": doctor.get("id"),
                        "name": _full_name(doctor) or "Доктор",
                    },
                    "services": [],
                    "is_cancelled": bool(v.get("is_cancelled", False)),
                    "_raw": v,
                }
            )
        return records

    async def get_record(self, record_id: int) -> Optional[dict[str, Any]]:
        try:
            visit = await self._make_request("GET", f"/visits/{record_id}")
            if isinstance(visit, dict):
                return visit
            return None
        except YClientsAPIError as e:
            logger.error("Failed to get visit %s: %s", record_id, e)
            return None

    async def _get_confirmed_status_id(self) -> Optional[int]:
        try:
            statuses = await self._make_request("GET", "/record_statuses")
        except YClientsAPIError:
            return None
        if not isinstance(statuses, list):
            return None
        for st in statuses:
            if not isinstance(st, dict):
                continue
            title = str(st.get("title", "")).lower()
            if "подтверж" in title:
                sid = st.get("id")
                return int(sid) if sid is not None else None
        return None

    async def update_record_status(
        self,
        record_id: int,
        status: str,
        comment: Optional[str] = None,
    ) -> bool:
        visit = await self.get_record(record_id)
        if not visit:
            return False

        if status == "deleted":
            reason = comment or "Отменено пациентом через Telegram"
            try:
                await self._make_request("POST", f"/visits/{record_id}/cancel", json={"reason": reason})
                return True
            except YClientsAPIError as e:
                logger.error("Failed to cancel visit %s: %s", record_id, e)
                return False

        if status == "confirmed":
            status_id = await self._get_confirmed_status_id()
            patient = visit.get("patient") if isinstance(visit.get("patient"), dict) else {}
            doctor = visit.get("doctor") if isinstance(visit.get("doctor"), dict) else {}
            chair = visit.get("chair") if isinstance(visit.get("chair"), dict) else {}

            payload: dict[str, Any] = {
                "branch_id": visit.get("branch_id") or self.branch_id,
                "patient_id": patient.get("id"),
                "doctor_id": doctor.get("id"),
                "chair_id": chair.get("id"),
                "start": visit.get("start"),
                "end": visit.get("end"),
                "description": visit.get("description") or comment or "Подтверждено пациентом",
                "type": visit.get("type"),
            }
            if status_id is not None:
                payload["status_id"] = status_id

            # Удаляем пустые поля
            payload = {k: v for k, v in payload.items() if v is not None}
            try:
                await self._make_request("PUT", f"/visits/{record_id}", json=payload)
                return True
            except YClientsAPIError as e:
                logger.error("Failed to confirm visit %s: %s", record_id, e)
                return False

        return False

    async def get_services(self) -> list[dict[str, Any]]:
        try:
            payload = await self._make_request("GET", "/services", params={"page": 1, "per_page": 200})
            if isinstance(payload, dict):
                return payload.get("data", [])
            return []
        except YClientsAPIError as e:
            logger.error("Failed to get services: %s", e)
            return []

    async def get_staff(self) -> list[dict[str, Any]]:
        try:
            payload = await self._make_request("GET", "/doctors", params={"page": 1, "per_page": 200})
            if isinstance(payload, dict):
                return payload.get("data", [])
            return []
        except YClientsAPIError as e:
            logger.error("Failed to get doctors: %s", e)
            return []

    async def find_client(
        self,
        phone: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        if not phone and not email:
            return None
        needle = phone or email or ""
        digits_needle = "".join(filter(str.isdigit, needle))
        params = {"search": needle, "page": 1, "per_page": 50}

        try:
            payload = await self._make_request("GET", "/patients", params=params)
        except YClientsAPIError as e:
            logger.error("Failed to find patient: %s", e)
            return None

        patients = payload.get("data", []) if isinstance(payload, dict) else []
        if not isinstance(patients, list):
            return None

        # Предпочитаем точное совпадение по телефону
        best: Optional[dict[str, Any]] = None
        for p in patients:
            if not isinstance(p, dict):
                continue
            phone_raw = str(p.get("phone") or "")
            p_digits = "".join(filter(str.isdigit, phone_raw))
            if digits_needle and p_digits and digits_needle in p_digits:
                best = p
                break
            if best is None:
                best = p

        if not best:
            return None
        return {
            "id": best.get("id"),
            "name": _full_name(best),
            "email": best.get("email", ""),
            "phone": best.get("phone", ""),
        }


yclients_client = YClientsClient()
