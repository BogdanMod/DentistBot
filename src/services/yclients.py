import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import aiohttp
from aiohttp import ClientError, ClientTimeout

from src.config import settings

logger = logging.getLogger(__name__)


class YClientsAPIError(Exception):
    """Базовая ошибка YClients API"""
    pass


class YClientsRateLimitError(YClientsAPIError):
    """Ошибка превышения лимита запросов"""
    pass


class YClientsClient:
    """Асинхронный клиент для YClients API"""

    def __init__(self):
        self.base_url = settings.YCLIENTS_API_URL
        self.company_id = settings.YCLIENTS_COMPANY_ID
        self.partner_token = settings.YCLIENTS_PARTNER_TOKEN
        self.user_token = settings.YCLIENTS_USER_TOKEN

        self.timeout = ClientTimeout(total=30)
        self._session: Optional[aiohttp.ClientSession] = None

        # Rate limiting
        self._request_times: list[datetime] = []
        self._max_requests_per_minute = 60

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение или создание HTTP сессии"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    def _get_headers(self) -> dict[str, str]:
        """Получение заголовков для запроса"""
        return {
            "Accept": "application/vnd.api.v2+json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.partner_token}, User {self.user_token}",
        }

    async def close(self) -> None:
        """Закрытие HTTP сессии"""
        if self._session and not self._session.closed:
            await self._session.close()
            
            
    async def _check_rate_limit(self) -> None:
        """Проверка и применение rate limiting"""
        now = datetime.now()

        # Удаляем запросы старше 1 минуты
        self._request_times = [
            t for t in self._request_times
            if now - t < timedelta(minutes=1)
        ]

        # Если достигнут лимит, ждём
        if len(self._request_times) >= self._max_requests_per_minute:
            wait_time = 60 - (now - self._request_times[0]).total_seconds()
            if wait_time > 0:
                logger.warning(
                    f"Rate limit reached. Waiting {wait_time:.2f} seconds..."
                )
                await asyncio.sleep(wait_time)
                self._request_times.clear()

        self._request_times.append(now)
        
        
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Выполнение HTTP запроса к API

        Args:
            method: HTTP метод (GET, POST, PUT, DELETE)
            endpoint: Endpoint API
            **kwargs: Дополнительные параметры для запроса

        Returns:
            Ответ от API в виде dict

        Raises:
            YClientsAPIError: При ошибке API
            YClientsRateLimitError: При превышении rate limit
        """
        await self._check_rate_limit()

        session = await self._get_session()
        url = f"{self.base_url}/{endpoint}"
        headers = self._get_headers()

        for attempt in range(1, 4):
            try:
                async with session.request(
                    method,
                    url,
                    headers=headers,
                    **kwargs,
                ) as response:
                    data = await response.json()
                    print(data)

                    if response.status == 429:
                        raise YClientsRateLimitError("Too many requests")

                    if response.status == 500:
                        if attempt < 3:
                            logger.warning(
                                f"Server error 500. Retrying in 1s (attempt {attempt}/3)..."
                            )
                            await asyncio.sleep(1)
                            continue
                        raise YClientsAPIError("HTTP 500")

                    if response.status >= 400:
                        error_msg = data.get("message", f"HTTP {response.status}")
                        logger.error(
                            f"YClients API error: {error_msg} (status: {response.status})"
                        )
                        raise YClientsAPIError(error_msg)

                    return data

            except ClientError as e:
                if attempt < 3:
                    logger.warning(
                        f"HTTP client error: {str(e)}. Retrying in 1s (attempt {attempt}/3)..."
                    )
                    await asyncio.sleep(1)
                    continue
                logger.error(f"HTTP client error: {str(e)}")
                raise YClientsAPIError(f"Connection error: {str(e)}")
        
        
    async def get_records(
        self,
        start_date: datetime,
        end_date: datetime,
        client_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Получение записей за период"""
        endpoint = f"records/{self.company_id}"
        params = {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
        }

        if client_id:
            params["client_id"] = client_id

        try:
            response = await self._make_request("GET", endpoint, params=params)
            return response.get("data", [])
        except YClientsAPIError as e:
            logger.error(f"Failed to get records: {str(e)}")
            return []
        
        
    async def get_record(self, record_id: int) -> Optional[dict[str, Any]]:
        """Получение информации о конкретной записи"""
        endpoint = f"record/{self.company_id}/{record_id}"

        try:
            response = await self._make_request("GET", endpoint)
            return response.get("data")
        except YClientsAPIError as e:
            logger.error(f"Failed to get record {record_id}: {str(e)}")
            return None
        
        
    async def update_record_status(
        self,
        record_id: int,
        status: str,
        comment: Optional[str] = None,
    ) -> bool:
        """
        Обновление статуса записи

        Args:
            record_id: ID записи
            status: Новый статус ('confirmed', 'deleted')
            comment: Комментарий (опционально)

        Returns:
            True если успешно, False иначе
        """
        endpoint = f"record/{self.company_id}/{record_id}"

        data: dict[str, Any] = {"attendance": 0}

        if status == "confirmed":
            data["attendance"] = 1
        elif status == "deleted":
            data["attendance"] = -1

        if comment:
            data["comment"] = comment

        try:
            await self._make_request("PUT", endpoint, json=data)
            logger.info(f"Record {record_id} status updated to {status}")
            return True
        except YClientsAPIError as e:
            logger.error(f"Failed to update record {record_id} status: {str(e)}")
            return False
        
        
    async def get_services(self) -> list[dict[str, Any]]:
        """Получение списка услуг компании"""
        endpoint = f"services/{self.company_id}"

        try:
            response = await self._make_request("GET", endpoint)
            return response.get("data", [])
        except YClientsAPIError as e:
            logger.error(f"Failed to get services: {str(e)}")
            return []
        
        
    async def get_staff(self) -> list[dict[str, Any]]:
        """Получение списка сотрудников"""
        endpoint = f"staff/{self.company_id}"

        try:
            response = await self._make_request("GET", endpoint)
            return response.get("data", [])
        except YClientsAPIError as e:
            logger.error(f"Failed to get staff: {str(e)}")
            return []
        
        
    async def find_client(
        self,
        phone: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Поиск клиента по телефону или email"""
        endpoint = f"clients/{self.company_id}"
        params = {}

        if phone:
            normalized = "".join(filter(str.isdigit, phone))
            params["phone"] = normalized
        elif email:
            params["email"] = email
        else:
            return None

        try:
            response = await self._make_request("GET", endpoint, params=params)
            clients = response.get("data", [])
            return clients[0] if clients else None
        except YClientsAPIError as e:
            logger.error(f"Failed to find client: {str(e)}")
            return None
        
        
yclients_client = YClientsClient()
