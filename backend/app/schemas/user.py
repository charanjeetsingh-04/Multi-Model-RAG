"""User-facing API schemas (request / response models)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: EmailStr
    username: str
    full_name: str | None
    is_active: bool
    is_admin: bool
    is_verified: bool
    created_at: datetime


class UserPreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    theme: str
    language: str
    preferred_response_style: str
    memory_facts: dict[str, Any]
    notes: str | None


class UserPreferenceUpdate(BaseModel):
    theme: str | None = None
    language: str | None = None
    preferred_response_style: str | None = None
    memory_facts: dict[str, Any] | None = None
    notes: str | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenRefresh(BaseModel):
    refresh_token: str
