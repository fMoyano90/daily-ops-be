from pydantic_settings import BaseSettings
from pydantic import model_validator
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "https://dailytaskops.netlify.app"]
    APP_NAME: str = "DailyOps API"
    APP_VERSION: str = "0.1.0"
    APP_TIMEZONE: str = "America/Santiago"

    JIRA_ENCRYPTION_KEY: str = ""
    JIRA_SYNC_ENABLED: bool = True
    JIRA_SYNC_INTERVAL_MINUTES: int = 30

    AUTO_CLOSE_ENABLED: bool = True
    AUTO_CLOSE_HOUR: int = 0
    AUTO_CLOSE_MINUTE: int = 1

    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    FOUNDER_EMAIL: str = "f.moyano90@gmail.com"
    FOUNDER_PASSWORD: str = ""
    FOUNDER_DISPLAY_NAME: str = "Felipe Moyano"

    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_CONTACT_EMAIL: str = "f.moyano90@gmail.com"

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-haiku-4-5-20251001"
    ANTHROPIC_TIMEOUT_SECONDS: float = 30.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def validate_secrets(self):
        if not self.JWT_SECRET_KEY:
            raise ValueError("JWT_SECRET_KEY must be set in environment")
        if not self.JIRA_ENCRYPTION_KEY:
            raise ValueError("JIRA_ENCRYPTION_KEY must be set in environment")
        return self


settings = Settings()
