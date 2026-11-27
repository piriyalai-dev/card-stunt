import asyncpg
from fastapi import APIRouter, Depends

from core.dependencies import get_current_user, get_db_pool
from models.stand_schemas import StandCreate, StandUpdate, StandResize, BlockedSeatsUpdate, StandOut
from services import stands_service
from routers._common import map_err, ensure_user

router = APIRouter(prefix="/stands", tags=["Stands"])


@router.get("/{stand_id}", response_model=StandOut)
async def get_stand(stand_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    ensure_user(user_ctx)
    try:
        return await stands_service.get_stand(pool, stand_id)
    except Exception as e:
        raise map_err(e)


@router.post("/{stand_id}/resize", response_model=StandOut)
async def resize_stand(stand_id: int, req: StandResize, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await stands_service.resize_stand(pool, uid, stand_id, req.model_dump())
    except Exception as e:
        raise map_err(e)


@router.patch("/{stand_id}/blocked-seats", response_model=StandOut)
async def set_blocked(stand_id: int, req: BlockedSeatsUpdate, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await stands_service.set_blocked(pool, uid, stand_id, req.blocked_seats)
    except Exception as e:
        raise map_err(e)
