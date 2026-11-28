import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from core.config import settings
from core.dependencies import get_db_pool, get_current_user
from core.exceptions import ForbiddenError, NotFoundError, RateLimitError
from models.auth_schemas import LoginRequest, LoginResponse, UserOut, ChangePasswordRequest
from services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """refresh token ลง httpOnly cookie — JS อ่านไม่ได้ (กัน XSS) · SameSite=Lax กัน CSRF ข้าม site."""
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=settings.REFRESH_COOKIE_SECURE,
        path="/api/v1/auth",
        max_age=settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(settings.REFRESH_COOKIE_NAME, path="/api/v1/auth")


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, response: Response, pool: asyncpg.Pool = Depends(get_db_pool)):
    try:
        user_id = await auth_service.authenticate_user(pool, req.username, req.password)
    except RateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except (NotFoundError, ForbiddenError) as e:
        raise HTTPException(status_code=401, detail=str(e))

    user = await auth_service.get_user_by_id(pool, user_id)
    access = auth_service.create_access_token(user_id, user["token_version"])
    refresh = auth_service.create_refresh_token(user_id, user["token_version"])
    _set_refresh_cookie(response, refresh)
    return LoginResponse(access_token=access, user=UserOut(**auth_service.make_user_out(user)))


@router.post("/refresh", response_model=LoginResponse)
async def refresh(request: Request, pool: asyncpg.Pool = Depends(get_db_pool)):
    """ขอ access token ใหม่ด้วย refresh cookie (httpOnly) — ไม่ต้อง login ซ้ำ."""
    refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="ไม่มี refresh token")
    try:
        user = await auth_service.validate_refresh_token(pool, refresh_token)
    except ForbiddenError as e:
        raise HTTPException(status_code=401, detail=str(e))
    access = auth_service.create_access_token(user["id"], user["token_version"])
    return LoginResponse(access_token=access, user=UserOut(**auth_service.make_user_out(user)))


@router.post("/logout", response_model=dict)
async def logout(response: Response):
    """ล้าง refresh cookie — access token (สั้น) หมดอายุเอง."""
    _clear_refresh_cookie(response)
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
async def get_me(user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    if not user_ctx.get("user_id"):
        raise HTTPException(status_code=401, detail="ไม่พบ user_id")
    user = await auth_service.get_user_by_id(pool, user_ctx["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้")
    return UserOut(**auth_service.make_user_out(user))


@router.post("/change-password", response_model=dict)
async def change_password(
    req: ChangePasswordRequest,
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    if not user_ctx.get("user_id"):
        raise HTTPException(status_code=401, detail="ไม่พบ user_id")
    if req.old_password == req.new_password:
        raise HTTPException(status_code=400, detail="รหัสผ่านใหม่ต้องไม่เหมือนรหัสเก่า")
    try:
        await auth_service.change_password(pool, user_ctx["user_id"], req.old_password, req.new_password)
    except (NotFoundError, ForbiddenError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "message": "เปลี่ยนรหัสผ่านสำเร็จ"}
