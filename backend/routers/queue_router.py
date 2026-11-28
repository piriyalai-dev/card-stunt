import asyncpg
from fastapi import APIRouter, Depends

from core.dependencies import get_current_user, get_db_pool
from models.queue_schemas import QueueInsertRequest, QueueReorderRequest
from routers._common import ensure_user, map_err
from services import queue_service

router = APIRouter(prefix="/events", tags=["Queue"])


@router.get("/{event_id}/queue")
async def get_queue(event_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await queue_service.get_queue(pool, uid, event_id)
    except Exception as e:
        raise map_err(e)


@router.put("/{event_id}/queue")
async def set_queue(event_id: int, req: QueueReorderRequest, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await queue_service.set_queue(pool, uid, event_id, req.order)
    except Exception as e:
        raise map_err(e)


@router.post("/{event_id}/queue/insert")
async def insert(event_id: int, req: QueueInsertRequest, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await queue_service.insert_stunt(pool, uid, event_id, req.stunt_id, req.position)
    except Exception as e:
        raise map_err(e)


@router.delete("/{event_id}/queue/{stunt_id}")
async def remove(event_id: int, stunt_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await queue_service.remove_stunt(pool, uid, event_id, stunt_id)
    except Exception as e:
        raise map_err(e)
