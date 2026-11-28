from datetime import datetime, timedelta, timezone
import uuid

import asyncpg
import bcrypt
from jose import jwt, JWTError

from core.config import settings
from core.exceptions import ForbiddenError, NotFoundError
from core.rbac import get_role_permissions, get_role_is_admin
from core.logger import AuditLogger
from core.ratelimit import check_login_rate_limit
from core.request_context import get_audit_context


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: int, token_version: int) -> str:
    """access token สั้น (นาที) — ใช้ยิง API ผ่าน Authorization header · ฝัง `ver` เพื่อ revoke ได้."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"user_id": user_id, "ver": token_version, "type": "access", "exp": expire},
        settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(user_id: int, token_version: int) -> str:
    """refresh token ยาว (วัน) — เก็บใน httpOnly cookie · ใช้ขอ access token ใหม่โดยไม่ login ซ้ำ."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"user_id": user_id, "ver": token_version, "type": "refresh",
         "jti": str(uuid.uuid4()), "exp": expire},
        settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM,
    )


async def validate_refresh_token(pool: asyncpg.Pool, refresh_token: str):
    """ตรวจ refresh token (type + exp + `ver` ตรง DB) → คืน user record หรือ raise ForbiddenError.

    ⚠️ `ver` != users.token_version ⇒ session ถูกเพิกถอน (เปลี่ยนรหัส/logout-all) ⇒ 401
    """
    try:
        payload = jwt.decode(refresh_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise ForbiddenError("refresh token ไม่ถูกต้องหรือหมดอายุ")
    if payload.get("type") != "refresh":
        raise ForbiddenError("token ไม่ใช่ refresh token")
    user_id = payload.get("user_id")
    ver = payload.get("ver")
    if user_id is None or ver is None:
        raise ForbiddenError("refresh token ไม่สมบูรณ์")

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, username, display_name, role, must_change_password, token_version"
            " FROM users WHERE id = $1 AND deleted_at IS NULL",
            user_id,
        )
    if row is None or int(row["token_version"]) != int(ver):
        raise ForbiddenError("เซสชันถูกเพิกถอน — กรุณาเข้าสู่ระบบใหม่")
    return row


async def authenticate_user(pool: asyncpg.Pool, username: str, password: str) -> int:
    # กัน brute-force: นับความพยายาม login ต่อ IP + ต่อ username (raise 429 เมื่อเกินเพดาน)
    ip = get_audit_context().get("ip_address") or "unknown"
    await check_login_rate_limit(ip, username)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, password_hash FROM users WHERE username = $1 AND deleted_at IS NULL",
            username,
        )
        if not row:
            await _audit_login(conn, username, None, False)
            raise NotFoundError("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
        if not verify_password(password, row["password_hash"]):
            await _audit_login(conn, username, row["id"], False)
            raise ForbiddenError("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
        await _audit_login(conn, username, row["id"], True)
        return row["id"]


async def _audit_login(conn, username, user_id, ok: bool) -> None:
    try:
        await AuditLogger("auth").log(
            conn, "LOGIN" if ok else "LOGIN_FAILED", username, "web",
            user_id=user_id, entity_type="user", entity_id=str(user_id) if user_id else None,
            status="success" if ok else "error",
        )
    except Exception:
        pass


async def change_password(pool: asyncpg.Pool, user_id: int, old_password: str, new_password: str) -> None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT password_hash FROM users WHERE id = $1 AND deleted_at IS NULL",
                user_id,
            )
            if not row:
                raise NotFoundError("ไม่พบผู้ใช้")
            if not verify_password(old_password, row["password_hash"]):
                raise ForbiddenError("รหัสผ่านเดิมไม่ถูกต้อง")
            await conn.execute(
                "UPDATE users SET password_hash = $1, must_change_password = FALSE,"
                " token_version = token_version + 1, updated_at = NOW() WHERE id = $2",
                hash_password(new_password), user_id,
            )
            await AuditLogger("auth").log(
                conn, "CHANGE_PASSWORD", str(user_id), "web",
                user_id=user_id, entity_type="user", entity_id=str(user_id),
            )


async def get_user_by_id(pool: asyncpg.Pool, user_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT id, username, display_name, role, must_change_password, token_version"
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
