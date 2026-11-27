import asyncpg
from fastapi import APIRouter, Depends, File, UploadFile

from core.dependencies import get_current_user, get_db_pool
from core.exceptions import ForbiddenError, NotFoundError
from models.stunt_schemas import StuntUpdate, StuntOut, GridUpdate, RevisionOut, StuntStats
from services import stunts_service
from routers._common import map_err, ensure_user

router = APIRouter(prefix="/stunts", tags=["Stunts"])


@router.get("/{stunt_id}", response_model=StuntOut)
async def get_stunt(stunt_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    ensure_user(user_ctx)
    try:
        return await stunts_service.get_stunt(pool, stunt_id)
    except Exception as e:
        raise map_err(e)


@router.patch("/{stunt_id}", response_model=StuntOut)
async def update_stunt(stunt_id: int, req: StuntUpdate, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await stunts_service.update_stunt(pool, uid, stunt_id, req.model_dump(exclude_unset=True))
    except Exception as e:
        raise map_err(e)


@router.delete("/{stunt_id}", response_model=dict)
async def delete_stunt(stunt_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        await stunts_service.delete_stunt(pool, uid, stunt_id)
        return {"status": "ok"}
    except Exception as e:
        raise map_err(e)


@router.put("/{stunt_id}/grid", response_model=StuntOut)
async def update_grid(stunt_id: int, req: GridUpdate, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await stunts_service.update_grid(pool, uid, stunt_id, req.model_dump())
    except Exception as e:
        raise map_err(e)


@router.get("/{stunt_id}/revisions", response_model=list[RevisionOut])
async def list_revisions(stunt_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await stunts_service.list_revisions(pool, stunt_id)
    except Exception as e:
        raise map_err(e)


@router.post("/{stunt_id}/revisions/{revision_id}/restore", response_model=StuntOut)
async def restore_revision(stunt_id: int, revision_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await stunts_service.restore_revision(pool, uid, stunt_id, revision_id)
    except Exception as e:
        raise map_err(e)


@router.post("/{stunt_id}/reference-image", response_model=StuntOut)
async def upload_reference(stunt_id: int, file: UploadFile = File(...), user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    content = await file.read()
    try:
        return await stunts_service.upload_reference(pool, uid, stunt_id, content, file.filename or "image.png")
    except Exception as e:
        raise map_err(e)


@router.get("/{stunt_id}/stats", response_model=StuntStats)
async def stats(stunt_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    ensure_user(user_ctx)
    try:
        return await stunts_service.stats(pool, stunt_id)
    except Exception as e:
        raise map_err(e)
