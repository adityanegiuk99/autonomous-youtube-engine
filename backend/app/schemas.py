from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    niche: str | None = Field(default=None, max_length=120)
    language: str = Field(default="en", min_length=2, max_length=16)
    target_country: str | None = Field(default=None, min_length=2, max_length=2)
    description: str | None = None
    is_active: bool = True


class ChannelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    niche: str | None = Field(default=None, max_length=120)
    language: str | None = Field(default=None, min_length=2, max_length=16)
    target_country: str | None = Field(default=None, min_length=2, max_length=2)
    description: str | None = None
    is_active: bool | None = None

    @field_validator("name", "language", "is_active")
    @classmethod
    def reject_null_for_required_fields(cls, value):
        if value is None:
            raise ValueError("This field cannot be null")
        return value


class ChannelRead(ChannelCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
