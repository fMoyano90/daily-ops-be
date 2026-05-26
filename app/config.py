from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    APP_NAME: str = "DailyOps API"
    APP_VERSION: str = "0.1.0"

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
