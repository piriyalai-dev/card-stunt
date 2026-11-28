from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class StuntCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    title: str = Field(..., min_length=1, max_length=200)
    section: Optional[str] = None
    notes: Optional[str] = None
    order_index: int = 0
    stand_id: Optional[int] = None
    side: str = Field("A", pattern="^(A|B)$")


class StuntUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    section: Optional[str] = None
    notes: Optional[str] = None
    order_index: Optional[int] = None
    status: Optional[str] = Field(None, pattern="^(draft|ready|published)$")
    side: Optional[str] = Field(None, pattern="^(A|B)$")
    reference_transform: Optional[dict] = None


class GridUpdate(BaseModel):
    grid_data: Optional[List] = None
    note: Optional[str] = None


class ReorderRequest(BaseModel):
    order: List[int]  # รายการ stunt id เรียงตามลำดับใหม่


class StuntOut(BaseModel):
    id: int
    event_id: int
    stand_id: int
    side: str
    code: str
    title: str
    section: Optional[str] = None
    notes: Optional[str] = None
    order_index: int
    status: str
    grid_width: int
    grid_height: int
    reference_image_path: Optional[str] = None
    reference_transform: Optional[dict] = None
    thumbnail_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class GridOut(BaseModel):
    grid_width: int
    grid_height: int
    grid_data: List[Optional[int]] = []


class RevisionOut(BaseModel):
    id: int
    revision_no: int
    grid_width: int
    grid_height: int
    note: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime


class StuntStats(BaseModel):
    total_cells: int
    filled: int
    color_counts: dict
