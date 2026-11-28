from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: Optional[str] = Field(None, pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    description: Optional[str] = None
    event_date: Optional[date] = None


class EventUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    slug: Optional[str] = Field(None, pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    description: Optional[str] = None
    event_date: Optional[date] = None
    status: Optional[str] = Field(None, pattern="^(draft|active|archived)$")
    public_access_enabled: Optional[bool] = None
    palette_a_id: Optional[int] = None
    palette_b_id: Optional[int] = None


class EventOut(BaseModel):
    id: int
    slug: str
    name: str
    description: Optional[str] = None
    event_date: Optional[date] = None
    status: str
    version: int
    published_version: int
    public_access_enabled: bool
    palette_a_id: Optional[int] = None
    palette_b_id: Optional[int] = None
    live_stunt_id: Optional[int] = None
    live_is_active: bool = False
    created_at: datetime
    updated_at: datetime


class DuplicateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: Optional[str] = Field(None, pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
