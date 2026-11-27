"""ตัวช่วยร่วมของ routers — map domain exception → HTTP + ดึง user_id."""
from fastapi import HTTPException

from core.exceptions import (
    NotFoundError, ForbiddenError, ValidationError, ConflictError,
    ServiceUnavailableError, PayloadTooLargeError, RateLimitError,
)


def map_err(e: Exception) -> HTTPException:
    if isinstance(e, NotFoundError):
        return HTTPException(status_code=404, detail=str(e))
    if isinstance(e, ForbiddenError):
        return HTTPException(status_code=403, detail=str(e))
    if isinstance(e, (ValidationError,)):
        return HTTPException(status_code=400, detail=str(e))
    if isinstance(e, ConflictError):
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, PayloadTooLargeError):
        return HTTPException(status_code=413, detail=str(e))
    if isinstance(e, RateLimitError):
        return HTTPException(status_code=429, detail=str(e))
    if isinstance(e, ServiceUnavailableError):
        return HTTPException(status_code=503, detail=str(e))
    return HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {e}")


def ensure_user(user_ctx: dict) -> int:
    """ดึง user_id หรือ raise 401 — internal read ทั้งหมดใช้ตัวนี้."""
    uid = user_ctx.get("user_id")
    if not uid:
        raise HTTPException(status_code=401, detail="ต้องเข้าสู่ระบบ")
    return int(uid)
