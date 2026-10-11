"""Pydantic-схемы ответов JSON API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GenerationOut(BaseModel):
    # from_attributes — можно собрать схему прямо из объекта SQLAlchemy
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    source_url: str
    cutout_url: str | None
    error_message: str | None
    created_at: datetime
