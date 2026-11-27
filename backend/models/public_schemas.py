from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class PublicPaletteColor(BaseModel):
    code: str
    name_th: str
    hex: str
    text_color: str


class PublicPalette(BaseModel):
    id: int
    name: str
    colors: List[PublicPaletteColor] = []


class PublicStand(BaseModel):
    id: int
    name: str
    rows: int
    cols: int
    sub_rows: int
    sub_cols: int
    row_label_style: str
    col_label_style: str
    row_label_prefix: str
    col_label_prefix: str
    blocked_seats: list


class PublicStuntSummary(BaseModel):
    id: int
    code: str
    title: str
    order_index: int
    status: str


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
    stands: List[PublicStand] = []
    palettes: List[PublicPalette] = []
    stunts: List[PublicStuntSummary] = []
    live: PublicLiveState


class PublicSeat(BaseModel):
    slug: str
    stand_id: int
    row_index: int
    col_index: int
    row_label: str
    seat_label: str
    student: Optional[dict] = None
    stunts: List[dict] = []  # ทุกฉาก published: {id, code, title, side_a, side_b}


class PublicVersion(BaseModel):
    published_version: int
    updated_at: datetime
