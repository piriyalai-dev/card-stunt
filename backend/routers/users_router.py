import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import get_current_user, get_db_pool
from core.exceptions import ForbiddenError, NotFoundError, ConflictError, ValidationError
from models.user_schemas import UserCreate, UserUpdate, UserOut
from services import users_service
from routers._common import map_err, ensure_user

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=list[UserOut])
async def list_users(user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await users_service.list_users(pool, uid)
    except Exception as e:
        raise map_err(e)


@router.post("", response_model=UserOut)
async def create_user(req: UserCreate, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await users_service.create_user(pool, uid, req.model_dump())
    except Exception as e:
        raise map_err(e)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: int, req: UserUpdate, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await users_service.update_user(pool, uid, user_id, req.model_dump(exclude_unset=True))
    except Exception as e:
        raise map_err(e)


@router.delete("/{user_id}", response_model=dict)
async def delete_user(user_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        await users_service.delete_user(pool, uid, user_id)
        return {"status": "ok"}
    except Exception as e:
        raise map_err(e)
