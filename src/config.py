import logging

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOG_LEVEL_ALIASES = {
    "ERRORS": "ERROR",
    "WARN": "WARNING",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file = ".env",
        env_file_encoding = "utf-8",
        case_sensitive = False,
        extra="ignore"
    )
    TELEGRAM_TOKEN: str
    ADMIN_CHAT_ID: int
    LOG_LEVEL: str

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        if not v:
            return "INFO"
        s = str(v).strip().upper()
        return _LOG_LEVEL_ALIASES.get(s, s)
    DEBUG: bool
    DATABASE_URL: str
    YCLIENTS_API_URL: str = "https://api.yclients.com/api/v1"
    YCLIENTS_COMPANY_ID: int
    YCLIENTS_PARTNER_TOKEN: str
    YCLIENTS_USER_TOKEN: str
    REMINDER_CHECK_TIME: str  # "HH:MM", например "10:00" — во сколько отправлять напоминания
    REMINDER_TIMEZONE: str = "UTC"  # таймзона для "завтра" и времени запуска (например Europe/Moscow)



settings = Settings()
