import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import PlanTier


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=200)


class UserRead(BaseModel):
    id: uuid.UUID
    email: EmailStr
    name: str
    avatar_url: str | None
    plan: PlanTier
    created_at: datetime

    model_config = {"from_attributes": True}
