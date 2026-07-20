import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from db_models.models.enums import AspectRatio, ProjectStatus


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    target_aspect_ratio: AspectRatio = AspectRatio.VERTICAL
    style_id: uuid.UUID | None = None
    instructions: str | None = Field(default=None, max_length=4000)


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    target_aspect_ratio: AspectRatio | None = None
    style_id: uuid.UUID | None = None
    instructions: str | None = Field(default=None, max_length=4000)


class ProjectRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    status: ProjectStatus
    target_aspect_ratio: AspectRatio
    style_id: uuid.UUID | None
    instructions: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
