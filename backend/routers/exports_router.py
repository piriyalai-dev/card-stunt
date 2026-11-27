import asyncpg
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from core.dependencies import get_current_user, get_db_pool
from models.export_schemas import ExportOut
from services import exports_service
from routers._common import map_err, ensure_user

router = APIRouter(prefix="/exports", tags=["Exports"])


@router.get("/{job_id}", response_model=ExportOut)
async def get_export(job_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await exports_service.get_export(pool, job_id, actor_id=uid)
    except Exception as e:
        raise map_err(e)


@router.post("/{job_id}/retry", response_model=ExportOut)
async def retry_export(job_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await exports_service.retry_export(pool, uid, job_id)
    except Exception as e:
        raise map_err(e)


@router.get("/{job_id}/download")
async def download_export(job_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        path, filename, media_type = await exports_service.download_export(pool, uid, job_id)
    except Exception as e:
        raise map_err(e)
    return FileResponse(path, media_type=media_type, filename=filename)
