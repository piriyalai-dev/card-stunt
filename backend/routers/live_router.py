import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional

from core.dependencies import get_current_user, get_db_pool
from services import live_service
from routers._common import map_err, ensure_user

router = APIRouter(prefix="/events", tags=["Live"])


class AdvanceRequest(BaseModel):
    action: str = Field(..., pattern="^(next|prev|goto)$")
    stunt_id: Optional[int] = None


@router.post("/{event_id}/live/advance")
async def advance(event_id: int, req: AdvanceRequest, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await live_service.advance(pool, uid, event_id, req.action, req.stunt_id)
    except Exception as e:
        raise map_err(e)
