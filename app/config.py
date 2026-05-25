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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
