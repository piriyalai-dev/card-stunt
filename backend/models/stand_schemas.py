from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class StandCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    rows: int = Field(..., gt=0)
    cols: int = Field(..., gt=0)
    sub_rows: int = Field(5, ge=1, le=16)
    sub_cols: int = Field(5, ge=1, le=16)
    seat_aspect_ratio: float = Field(1.0, ge=0.4, le=2.5)
    row_direction: str = Field("bottom_to_top", pattern="^(bottom_to_top|top_to_bottom)$")
    col_direction: str = Field("left_to_right", pattern="^(left_to_right|right_to_left)$")
    row_label_style: str = Field("alpha", pattern="^(numeric|alpha)$")
    col_label_style: str = Field("numeric", pattern="^(numeric|alpha)$")
    row_label_prefix: str = ""
    col_label_prefix: str = ""
    blocked_seats: List[dict] = []


class StandUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    seat_aspect_ratio: Optional[float] = Field(None, ge=0.4, le=2.5)
    row_direction: Optional[str] = Field(None, pattern="^(bottom_to_top|top_to_bottom)$")
    col_direction: Optional[str] = Field(None, pattern="^(left_to_right|right_to_left)$")
    row_label_style: Optional[str] = Field(None, pattern="^(numeric|alpha)$")
    col_label_style: Optional[str] = Field(None, pattern="^(numeric|alpha)$")
    row_label_prefix: Optional[str] = None
    col_label_prefix: Optional[str] = None


class StandResize(BaseModel):
    rows: int = Field(..., gt=0)
    cols: int = Field(..., gt=0)
    sub_rows: Optional[int] = Field(None, ge=1, le=16)
    sub_cols: Optional[int] = Field(None, ge=1, le=16)
    allow_crop: bool = False


class BlockedSeatsUpdate(BaseModel):
    blocked_seats: List[dict]


class StandOut(BaseModel):
    id: int
    event_id: int
    name: str
    rows: int
    cols: int
    sub_rows: int
    sub_cols: int
    seat_aspect_ratio: float
    row_direction: str
    col_direction: str
    row_label_style: str
    col_label_style: str
    row_label_prefix: str
    col_label_prefix: str
    blocked_seats: list
    grid_width: int
    grid_height: int
    created_at: datetime
    updated_at: datetime
