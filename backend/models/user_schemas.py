from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from models.password import validate_password_strength


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(...)
    display_name: Optional[str] = None
    role: str = Field("staff", pattern="^(admin|designer|staff)$")

    _validate_password = field_validator("password")(validate_password_strength)


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = Field(None, pattern="^(admin|designer|staff)$")
    password: Optional[str] = Field(None)

    _validate_password = field_validator("password")(validate_password_strength)


class UserOut(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    role: str
    is_admin: bool = False
    permissions: List[str] = []
    must_change_password: bool = False
