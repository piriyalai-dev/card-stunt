from typing import Optional

import asyncpg
from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from core.config import settings

bearer_auth = HTTPBearer(auto_error=False)

# เส้นทางที่ยังใช้ได้แม้ `must_change_password` ยังจริง (ต้องยอมให้เรียกเพื่อเปลี่ยนรหัส)
_PASSWORD_CHANGE_ALLOWED = {"/api/v1/auth/me", "/api/v1/auth/change-password"}


async def get_db_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.db_pool


# 🚀 แปลงทุก Request ให้เป็น user_id ผ่าน JWT Bearer token
async def get_current_user(
    request: Request,
    auth: Optional[HTTPAuthorizationCredentials] = Security(bearer_auth),
) -> dict:
    """JWT Bearer → {"user_id", "must_change_password"} · revalidate ว่า user ยัง active อยู่.

    - token หมดอายุ/ไม่ถูกต้อง → 401
    - user ถูกลบ (soft delete) → 401 (token เก่าใช้ต่อไม่ได้ — กัน token อายุ 30 วันหลุด)
    - `must_change_password` ยังจริง → 403 ยกเว้น `/auth/me` + `/auth/change-password`
      (บังคับเปลี่ยนรหัสฝั่ง server ไม่ใช่แค่ฝั่ง frontend)
    """
    if not auth:
        raise HTTPException(status_code=401, detail="Not authenticated: Bearer Token required")
    try:
        payload = jwt.decode(auth.credentials, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # refresh token ห้ามใช้เป็น access token
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token: not an access token")
    user_id = payload.get("user_id")
    ver = payload.get("ver")
    if user_id is None or ver is None:
        raise HTTPException(status_code=401, detail="Invalid token: Missing claims")

    pool = request.app.state.db_pool
    row = await pool.fetchrow(
        "SELECT must_change_password, token_version FROM users WHERE id = $1 AND deleted_at IS NULL",
        int(user_id),
    )
    # row None = user ถูกลบ · ver ไม่ตรง = session ถูกเพิกถอน (เปลี่ยนรหัส/logout-all)
    if row is None or int(row["token_version"]) != int(ver):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    must_change = bool(row["must_change_password"])
    if must_change and request.url.path not in _PASSWORD_CHANGE_ALLOWED:
        raise HTTPException(status_code=403, detail="ต้องเปลี่ยนรหัสผ่านก่อนใช้งาน")

    return {"user_id": int(user_id), "must_change_password": must_change}
