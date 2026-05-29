from datetime import date

from app.schemas.sleep_log import SleepLogCreate


def test_sleep_log_create_accepts_date_string():
    data = SleepLogCreate(date="2026-05-29", hours_slept=7.5, sleep_quality=8)

    assert data.date == date(2026, 5, 29)


def test_sleep_log_create_date_schema_allows_string_date_or_null():
    date_schema = SleepLogCreate.model_json_schema()["properties"]["date"]

    assert date_schema["anyOf"] == [{"format": "date", "type": "string"}, {"type": "null"}]
