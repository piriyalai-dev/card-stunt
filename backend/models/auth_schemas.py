from typing import List, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., description="username")
    password: str = Field(..., min_length=4, description="รหัสผ่าน")


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., description="รหัสผ่านเดิม")
    new_password: str = Field(..., min_length=4, description="รหัสผ่านใหม่")


class UserOut(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    role: Optional[str] = None
    is_admin: bool = False
    permissions: List[str] = []
    must_change_password: bool = False


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
