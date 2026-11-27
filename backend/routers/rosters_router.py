import asyncpg
from fastapi import APIRouter, Depends, File, UploadFile, Form

from core.dependencies import get_current_user, get_db_pool
from models.roster_schemas import RosterCreate, RosterUpdate, RosterOut
from services import rosters_service
from routers._common import map_err, ensure_user

router = APIRouter(prefix="/rosters", tags=["Rosters"])


@router.get("/{roster_id}", response_model=RosterOut)
async def get_roster(roster_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    ensure_user(user_ctx)
    try:
        return await rosters_service.get_roster(pool, roster_id)
    except Exception as e:
        raise map_err(e)


@router.patch("/{roster_id}", response_model=RosterOut)
async def update_roster(roster_id: int, req: RosterUpdate, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await rosters_service.update_roster(pool, uid, roster_id, req.model_dump(exclude_unset=True))
    except Exception as e:
        raise map_err(e)


@router.delete("/{roster_id}", response_model=dict)
async def delete_roster(roster_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        await rosters_service.delete_roster(pool, uid, roster_id)
        return {"status": "ok"}
    except Exception as e:
        raise map_err(e)
