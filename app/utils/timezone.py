from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import settings


def app_tz() -> ZoneInfo:
    return ZoneInfo(settings.APP_TIMEZONE)


def local_now() -> datetime:
    return datetime.now(app_tz())


def local_today() -> date:
    return local_now().date()
