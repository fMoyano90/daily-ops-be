from datetime import datetime, date, time, timezone
from typing import Optional, List, Any
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator, computed_field

from app.models.daily_task import DailyTaskStatus
from app.models.task import Priority
from app.schemas.daily_subtask import DailySubtaskResponse
from app.schemas.emotion import EmotionEntryResponse
from app.schemas.project import ProjectResponse
from app.schemas.recurring_task import RecurringTaskResponse
from app.schemas.rich_text import RichTextAttachmentResponse


class DailyTaskCreate(BaseModel):
    task_id: Optional[UUID] = None
    recurring_task_id: Optional[UUID] = None
    priority: Priority = Priority.medium


class DailyTaskUpdate(BaseModel):
    status: Optional[DailyTaskStatus] = None
    priority: Optional[Priority] = None
    estimated_seconds: Optional[int] = Field(default=None, ge=0)
    sort_order: Optional[int] = None


class DailyTaskResponse(BaseModel):
    id: UUID
    daily_plan_id: UUID
    task_id: Optional[UUID]
    recurring_task_id: Optional[UUID] = None
    title_snapshot: str
    description: Optional[str] = None
    description_doc: Optional[dict[str, Any]] = None
    description_attachments: List[RichTextAttachmentResponse] = []
    external_key: Optional[str] = None
    external_url: Optional[str] = None
    tag: Optional[str] = None
    category: Optional[str] = None
    due_date: Optional[date] = None
    meeting_time: Optional[time] = None
    reminder_minutes_before: Optional[int] = None
    priority: Priority
    status: DailyTaskStatus
    estimated_seconds: Optional[int] = None
    total_seconds: int
    live_total_seconds: int = 0
    sort_order: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    subtasks: List[DailySubtaskResponse] = []
    emotion_entries: List[EmotionEntryResponse] = []
    project: Optional[ProjectResponse] = None
    recurring_task: Optional[RecurringTaskResponse] = None

    model_config = {"from_attributes": True}

    timer_sessions: List[Any] = Field(default_factory=list, exclude=True)

    @property
    def is_recurring(self) -> bool:
        return self.recurring_task_id is not None

    @model_validator(mode="before")
    @classmethod
    def extract_project_from_task(cls, data):
        if isinstance(data, dict):
            if data.get("project") is None:
                if data.get("task"):
                    task = data["task"]
                    if hasattr(task, "project"):
                        data = dict(data)
                        data["project"] = task.project
                elif data.get("recurring_task"):
                    rt = data["recurring_task"]
                    if hasattr(rt, "project"):
                        data = dict(data)
                        data["project"] = rt.project
            if data.get("description") is None:
                task = data.get("task")
                if task and hasattr(task, "description"):
                    data = dict(data)
                    data["description"] = task.description
                else:
                    rt = data.get("recurring_task")
                    if rt and hasattr(rt, "description"):
                        data = dict(data)
                        data["description"] = rt.description
            if data.get("description_doc") is None:
                task = data.get("task")
                if task and hasattr(task, "description_doc"):
                    data = dict(data)
                    data["description_doc"] = task.description_doc
                    data["description_attachments"] = getattr(task, "description_attachments", [])
                else:
                    rt = data.get("recurring_task")
                    if rt and hasattr(rt, "description_doc"):
                        data = dict(data)
                        data["description_doc"] = rt.description_doc
                        data["description_attachments"] = getattr(rt, "description_attachments", [])
            if data.get("external_key") is None or data.get("external_url") is None:
                task = data.get("task")
                if task:
                    data = dict(data)
                    if data.get("external_key") is None and hasattr(task, "external_key"):
                        data["external_key"] = task.external_key
                    if data.get("external_url") is None and hasattr(task, "external_url"):
                        data["external_url"] = task.external_url
                else:
                    rt = data.get("recurring_task")
                    if rt and data.get("external_url") is None and hasattr(rt, "external_url"):
                        data = dict(data)
                        data["external_url"] = rt.external_url
            if data.get("tag") is None:
                rt = data.get("recurring_task")
                if rt and getattr(rt, "tag", None):
                    data = dict(data)
                    data["tag"] = rt.tag
            if data.get("category") is None:
                task = data.get("task")
                if task and getattr(task, "category", None):
                    data = dict(data)
                    data["category"] = task.category
                else:
                    rt = data.get("recurring_task")
                    if rt and getattr(rt, "category", None):
                        data = dict(data)
                        data["category"] = rt.category
            if data.get("meeting_time") is None:
                task = data.get("task")
                if task and getattr(task, "meeting_time", None):
                    data = dict(data)
                    data["meeting_time"] = task.meeting_time
                else:
                    rt = data.get("recurring_task")
                    if rt and getattr(rt, "meeting_time", None):
                        data = dict(data)
                        data["meeting_time"] = rt.meeting_time
            if data.get("due_date") is None:
                task = data.get("task")
                if task and getattr(task, "due_date", None):
                    data = dict(data)
                    data["due_date"] = task.due_date
            if data.get("reminder_minutes_before") is None:
                task = data.get("task")
                if task and getattr(task, "reminder_minutes_before", None) is not None:
                    data = dict(data)
                    data["reminder_minutes_before"] = task.reminder_minutes_before
                else:
                    rt = data.get("recurring_task")
                    if rt and getattr(rt, "reminder_minutes_before", None) is not None:
                        data = dict(data)
                        data["reminder_minutes_before"] = rt.reminder_minutes_before
        elif hasattr(data, "__dict__"):
            if getattr(data, "project", None) is None:
                task = getattr(data, "task", None)
                if task:
                    project = getattr(task, "project", None)
                    if project:
                        data.__dict__["project"] = project
                else:
                    rt = getattr(data, "recurring_task", None)
                    if rt:
                        project = getattr(rt, "project", None)
                        if project:
                            data.__dict__["project"] = project
            if getattr(data, "description", None) is None:
                task = getattr(data, "task", None)
                if task and getattr(task, "description", None):
                    data.__dict__["description"] = task.description
                else:
                    rt = getattr(data, "recurring_task", None)
                    if rt and getattr(rt, "description", None):
                        data.__dict__["description"] = rt.description
            if getattr(data, "description_doc", None) is None:
                task = getattr(data, "task", None)
                if task and getattr(task, "description_doc", None):
                    data.__dict__["description_doc"] = task.description_doc
                    data.__dict__["description_attachments"] = getattr(task, "description_attachments", [])
                else:
                    rt = getattr(data, "recurring_task", None)
                    if rt and getattr(rt, "description_doc", None):
                        data.__dict__["description_doc"] = rt.description_doc
                        data.__dict__["description_attachments"] = getattr(rt, "description_attachments", [])
            task = getattr(data, "task", None)
            if task:
                if getattr(data, "external_key", None) is None and getattr(task, "external_key", None):
                    data.__dict__["external_key"] = task.external_key
                if getattr(data, "external_url", None) is None and getattr(task, "external_url", None):
                    data.__dict__["external_url"] = task.external_url
                if getattr(data, "category", None) is None and getattr(task, "category", None):
                    data.__dict__["category"] = task.category
                if getattr(data, "due_date", None) is None and getattr(task, "due_date", None):
                    data.__dict__["due_date"] = task.due_date
                if getattr(data, "meeting_time", None) is None and getattr(task, "meeting_time", None):
                    data.__dict__["meeting_time"] = task.meeting_time
            else:
                rt = getattr(data, "recurring_task", None)
                if rt:
                    if getattr(data, "external_url", None) is None and getattr(rt, "external_url", None):
                        data.__dict__["external_url"] = rt.external_url
                    if getattr(data, "meeting_time", None) is None and getattr(rt, "meeting_time", None):
                        data.__dict__["meeting_time"] = rt.meeting_time
                    if getattr(data, "tag", None) is None and getattr(rt, "tag", None):
                        data.__dict__["tag"] = rt.tag
            if getattr(data, "category", None) is None:
                rt = getattr(data, "recurring_task", None)
                if rt and getattr(rt, "category", None):
                    data.__dict__["category"] = rt.category
            if getattr(data, "reminder_minutes_before", None) is None:
                task = getattr(data, "task", None)
                if task and getattr(task, "reminder_minutes_before", None) is not None:
                    data.__dict__["reminder_minutes_before"] = task.reminder_minutes_before
                else:
                    rt = getattr(data, "recurring_task", None)
                    if rt and getattr(rt, "reminder_minutes_before", None) is not None:
                        data.__dict__["reminder_minutes_before"] = rt.reminder_minutes_before
        return data
