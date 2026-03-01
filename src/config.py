from pydantic_settings import BaseSettings, SettingsConfigDict

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
    DEBUG: bool
    DATABASE_URL: str
    YCLIENTS_API_URL: str = "https://api.yclients.com/api/v1"
    YCLIENTS_COMPANY_ID: int
    YCLIENTS_PARTNER_TOKEN: str
    YCLIENTS_USER_TOKEN: str
    REMINDER_HOURS_BEFORE: int
    REMINDER_CHECK_TIME: str



settings = Settings()
