from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

from app.models.project import ProjectType


class ProjectCreate(BaseModel):
    name: str
    type: ProjectType
    color: str


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[ProjectType] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    type: ProjectType
    color: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
