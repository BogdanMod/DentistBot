from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

import httpx


class YclientsNotConfiguredError(RuntimeError):
    pass


@dataclass(frozen=True)
class YclientsConfig:
    base_url: str
    partner_token: str
    user_token: str | None
    company_id: str
    branch_id: str | None

    @classmethod
    def from_env(cls) -> "YclientsConfig":
        return cls(
            base_url=os.getenv("YCLIENTS_BASE_URL", "https://api.yclients.com/api/v1"),
            partner_token=os.getenv("YCLIENTS_PARTNER_TOKEN", ""),
            user_token=os.getenv("YCLIENTS_USER_TOKEN") or None,
            company_id=os.getenv("YCLIENTS_COMPANY_ID", ""),
            branch_id=os.getenv("YCLIENTS_BRANCH_ID") or None,
        )


class YclientsClient:
    def __init__(self, config: YclientsConfig) -> None:
        self._config = config

    @property
    def config(self) -> YclientsConfig:
        return self._config

    def is_configured(self) -> bool:
        return bool(self._config.partner_token and self._config.company_id)

    def _headers(self) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._config.partner_token}"}
        if self._config.user_token:
            headers["User-Token"] = self._config.user_token
        return headers

    async def request(
        self, method: str, path: str, *, params: dict[str, Any] | None = None, json: Any | None = None
    ) -> dict[str, Any]:
        if not self.is_configured():
            raise YclientsNotConfiguredError("Yclients не настроен")

        url = f"{self._config.base_url.rstrip('/')}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self._headers(),
                params=params,
                json=json,
            )
            response.raise_for_status()
            return response.json()


