from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file = ".env",
        env_file_encoding = "utf-8",
        case_sensitive = False
    )
    TELEGRAM_TOKEN: str
    ADMIN_ID: str
    LOG_LEVEL: str
    DEBUG: bool


settings = Settings()
