from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ColorCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name_th: str = Field(..., min_length=1, max_length=100)
    hex: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")
    text_color: str = Field("#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    order_index: int = 0


class ColorUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=1, max_length=20)
    name_th: Optional[str] = Field(None, min_length=1, max_length=100)
    hex: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    text_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    order_index: Optional[int] = None


class ColorDelete(BaseModel):
    replacement_color_id: Optional[int] = None


class PaletteCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    is_default: bool = False
    colors: List[ColorCreate] = []


class PaletteUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    is_default: Optional[bool] = None


class ColorOut(BaseModel):
    id: int
    code: str
    name_th: str
    hex: str
    text_color: str
    order_index: int


class PaletteOut(BaseModel):
    id: int
    event_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    is_default: bool
    colors: List[ColorOut] = []
    created_at: datetime
    updated_at: datetime
