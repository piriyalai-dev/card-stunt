from typing import List, Optional

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=4)
    display_name: Optional[str] = None
    role: str = Field("staff", pattern="^(admin|designer|staff)$")


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = Field(None, pattern="^(admin|designer|staff)$")
    password: Optional[str] = Field(None, min_length=4)


class UserOut(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    role: str
    is_admin: bool = False
    permissions: List[str] = []
    must_change_password: bool = False
