from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.recurring_task import RecurringTaskType
from app.schemas.recurring_task import RecurringTaskCreate, RecurringTaskUpdate
from app.schemas.task import TaskCreate, TaskUpdate


@pytest.mark.parametrize(
    "schema_factory",
    [
        lambda value: TaskCreate(project_id=uuid4(), title="Task", external_url=value),
        lambda value: TaskUpdate(external_url=value),
        lambda value: RecurringTaskCreate(
            project_id=uuid4(),
            title="Recurring task",
            external_url=value,
            recurrence_type=RecurringTaskType.weekly,
        ),
        lambda value: RecurringTaskUpdate(external_url=value),
    ],
)
def test_external_url_accepts_http_urls(schema_factory):
    schema = schema_factory(" https://example.com/path ")

    assert schema.external_url == "https://example.com/path"


@pytest.mark.parametrize(
    "value",
    [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
        "//example.com/path",
        "/relative/path",
        "example.com/path",
        "https://example.com\njavascript:alert(1)",
    ],
)
def test_task_external_url_rejects_unsafe_urls(value):
    with pytest.raises(ValidationError):
        TaskCreate(project_id=uuid4(), title="Task", external_url=value)


def test_external_url_blank_becomes_none():
    schema = RecurringTaskUpdate(external_url="   ")

    assert schema.external_url is None
