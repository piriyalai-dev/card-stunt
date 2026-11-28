from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel


class PublicPaletteColor(BaseModel):
    id: int
    code: str
    name_th: str
    hex: str
    text_color: str


class PublicPalette(BaseModel):
    id: int
    name: str
    colors: List[PublicPaletteColor] = []


class PublicLiveState(BaseModel):
    stunt_id: Optional[int] = None
    stunt_index: Optional[int] = None
    total: int
    is_active: bool
    published_version: int


class PublicMeta(BaseModel):
    slug: str
    name: str
    published_version: int
    event_date: Optional[date] = None
    live: PublicLiveState


class PublicSeatStunt(BaseModel):
    id: int
    code: str
    title: str
    notes: Optional[str] = None
    side: str
    plate: List[List[Optional[int]]] = []


class PublicSeat(BaseModel):
    slug: str
    stand_id: int
    row_index: int
    col_index: int
    row_label: str
    seat_label: str
    student: Optional[dict] = None
    palettes: List[PublicPalette] = []
    stunts: List[PublicSeatStunt] = []


class PublicVersion(BaseModel):
    published_version: int
    updated_at: datetime
