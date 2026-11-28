from pydantic import BaseModel, Field, field_validator

from models.password import validate_password_strength
from models.user_schemas import UserOut


class LoginRequest(BaseModel):
    username: str = Field(..., description="username")
    password: str = Field(..., min_length=1, description="รหัสผ่าน")


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., description="รหัสผ่านเดิม")
    new_password: str = Field(..., description="รหัสผ่านใหม่")

    _validate_new_password = field_validator("new_password")(validate_password_strength)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
