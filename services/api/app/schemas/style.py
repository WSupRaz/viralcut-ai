import uuid

from pydantic import BaseModel


class StyleRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_system: bool

    model_config = {"from_attributes": True}
