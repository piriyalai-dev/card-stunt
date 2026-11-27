from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RosterCreate(BaseModel):
    stand_id: int
    row_index: int = Field(..., ge=0)
    col_index: int = Field(..., ge=0)
    student_code: Optional[str] = None
    student_name: str = Field(..., min_length=1, max_length=200)
    note: Optional[str] = None


class RosterUpdate(BaseModel):
    student_code: Optional[str] = None
    student_name: Optional[str] = Field(None, min_length=1, max_length=200)
    note: Optional[str] = None


class RosterOut(BaseModel):
    id: int
    event_id: int
    stand_id: int
    row_index: int
    col_index: int
    row_label: Optional[str] = None
    seat_label: Optional[str] = None
    student_code: Optional[str] = None
    student_name: str
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime
