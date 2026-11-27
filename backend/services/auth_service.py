from datetime import datetime, timedelta, timezone

import asyncpg
import bcrypt
from jose import jwt

from core.config import settings
from core.exceptions import ForbiddenError, NotFoundError
from core.rbac import get_role_permissions, get_role_is_admin


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"user_id": user_id, "exp": expire}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


async def authenticate_user(pool: asyncpg.Pool, username: str, password: str) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, password_hash FROM users WHERE username = $1 AND deleted_at IS NULL",
            username,
        )
        if not row:
            raise NotFoundError("ไม่พบชื่อผู้ใช้นี้ หรือรหัสผ่านไม่ถูกต้อง")
        if not verify_password(password, row["password_hash"]):
            raise ForbiddenError("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
        return row["id"]


async def change_password(pool: asyncpg.Pool, user_id: int, old_password: str, new_password: str) -> None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT password_hash FROM users WHERE id = $1 AND deleted_at IS NULL",
            user_id,
        )
        if not row:
            raise NotFoundError("ไม่พบผู้ใช้")
        if not verify_password(old_password, row["password_hash"]):
            raise ForbiddenError("รหัสผ่านเดิมไม่ถูกต้อง")
        await conn.execute(
            "UPDATE users SET password_hash = $1, must_change_password = FALSE, updated_at = NOW() WHERE id = $2",
            hash_password(new_password), user_id,
        )


async def get_user_by_id(pool: asyncpg.Pool, user_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, username, display_name, role, must_change_password"
            " FROM users WHERE id = $1 AND deleted_at IS NULL",
            user_id,
        )


def make_user_out(user_record) -> dict:
    role = user_record["role"]
    return {
        "id": user_record["id"],
        "username": user_record["username"],
        "display_name": user_record["display_name"],
        "role": role,
        "is_admin": get_role_is_admin(role),
        "permissions": get_role_permissions(role),
        "must_change_password": bool(user_record["must_change_password"]),
    }
