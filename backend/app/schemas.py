from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    niche: str | None = Field(default=None, max_length=120)
    language: str = Field(default="en", min_length=2, max_length=16)
    target_country: str | None = Field(default=None, min_length=2, max_length=2)
    description: str | None = None
    audience_profile: str | None = Field(default=None, max_length=2000)
    brand_voice: str | None = Field(default=None, max_length=1000)
    visual_guidelines: str | None = Field(default=None, max_length=2000)
    content_pillars: list[str] = Field(default_factory=list, max_length=10)
    preferred_formats: list[Literal["short", "long"]] = Field(default_factory=lambda: ["short", "long"], min_length=1, max_length=2)
    publishing_frequency_per_week: int | None = Field(default=None, ge=0, le=14)
    is_active: bool = True

    @field_validator("content_pillars")
    @classmethod
    def clean_content_pillars(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value or len(value) > 120 for value in cleaned) or len({v.casefold() for v in cleaned}) != len(cleaned):
            raise ValueError("Content pillars must be unique, non-empty values up to 120 characters")
        return cleaned

    @field_validator("preferred_formats")
    @classmethod
    def unique_formats(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("Preferred formats must be unique")
        return values


class ChannelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    niche: str | None = Field(default=None, max_length=120)
    language: str | None = Field(default=None, min_length=2, max_length=16)
    target_country: str | None = Field(default=None, min_length=2, max_length=2)
    description: str | None = None
    audience_profile: str | None = Field(default=None, max_length=2000)
    brand_voice: str | None = Field(default=None, max_length=1000)
    visual_guidelines: str | None = Field(default=None, max_length=2000)
    content_pillars: list[str] | None = Field(default=None, max_length=10)
    preferred_formats: list[Literal["short", "long"]] | None = Field(default=None, min_length=1, max_length=2)
    publishing_frequency_per_week: int | None = Field(default=None, ge=0, le=14)
    is_active: bool | None = None

    @field_validator("name", "language", "is_active")
    @classmethod
    def reject_null_for_required_fields(cls, value):
        if value is None:
            raise ValueError("This field cannot be null")
        return value

    @field_validator("content_pillars")
    @classmethod
    def clean_content_pillars(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return values
        cleaned = [value.strip() for value in values]
        if any(not value or len(value) > 120 for value in cleaned) or len({v.casefold() for v in cleaned}) != len(cleaned):
            raise ValueError("Content pillars must be unique, non-empty values up to 120 characters")
        return cleaned

    @field_validator("preferred_formats")
    @classmethod
    def unique_formats(cls, values: list[str] | None) -> list[str] | None:
        if values is not None and (not values or len(set(values)) != len(values)):
            raise ValueError("Preferred formats must be unique and include at least one format")
        return values

    @field_validator("content_pillars", "preferred_formats")
    @classmethod
    def reject_null_for_lists(cls, value):
        if value is None:
            raise ValueError("This field cannot be null; use an empty list when clearing content pillars")
        return value


class ChannelRead(ChannelCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
