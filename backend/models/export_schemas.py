from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ExportCreate(BaseModel):
    format: str = Field(..., pattern="^(pdf|csv|zip)$")
    scope: str = Field("event", max_length=50)
    stand_id: Optional[int] = None


class ExportOut(BaseModel):
    id: int
    event_id: int
    stand_id: Optional[int] = None
    format: str
    scope: str
    status: str
    file_path: Optional[str] = None
    error: Optional[str] = None
    requested_by: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
