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
    # ID администратора: всегда из кода, .env не используется
    ADMIN_CHAT_ID: int = 6549458615
    LOG_LEVEL: str

    @field_validator("ADMIN_CHAT_ID", mode="before")
    @classmethod
    def _admin_chat_id_always_from_code(cls, _v: object) -> int:
        return 6549458615

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        if not v:
            return "INFO"
        s = str(v).strip().upper()
        return _LOG_LEVEL_ALIASES.get(s, s)
    DEBUG: bool
    DATABASE_URL: str
    DENTIST_PLUS_API_URL: str = "https://api2.dentist-plus.com/partner"
    DENTIST_PLUS_LOGIN: str = ""
    DENTIST_PLUS_PASSWORD: str = ""
    DENTIST_PLUS_BRANCH_ID: int = 0  # 0 => не фильтровать по филиалу
    REMINDER_CHECK_TIME: str  # "HH:MM", например "10:00" — во сколько отправлять напоминания
    REMINDER_TIMEZONE: str = "UTC"  # таймзона для "завтра" и времени запуска (например Europe/Moscow)
    REMINDER_SIGNATURE: str = "команда доктора Шевцовой🦷"
    RESCHEDULE_CONTACT: str = "@Shevtsova_team"


settings = Settings()
