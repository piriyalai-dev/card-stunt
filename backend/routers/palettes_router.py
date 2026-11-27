import asyncpg
from fastapi import APIRouter, Depends

from core.dependencies import get_current_user, get_db_pool
from models.palette_schemas import (
    PaletteCreate, PaletteUpdate, PaletteOut, ColorCreate, ColorUpdate, ColorDelete, ColorOut,
)
from services import palettes_service
from routers._common import map_err, ensure_user

router = APIRouter(prefix="/palettes", tags=["Palettes"])


@router.get("/{palette_id}", response_model=PaletteOut)
async def get_palette(palette_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    ensure_user(user_ctx)
    try:
        return await palettes_service.get_palette(pool, palette_id)
    except Exception as e:
        raise map_err(e)


@router.patch("/{palette_id}", response_model=PaletteOut)
async def update_palette(palette_id: int, req: PaletteUpdate, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await palettes_service.update_palette(pool, uid, palette_id, req.model_dump(exclude_unset=True))
    except Exception as e:
        raise map_err(e)


@router.delete("/{palette_id}", response_model=dict)
async def delete_palette(palette_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        await palettes_service.delete_palette(pool, uid, palette_id)
        return {"status": "ok"}
    except Exception as e:
        raise map_err(e)


# ── colors ─────────────────────────────────────────────────────────

@router.post("/{palette_id}/colors", response_model=ColorOut)
async def add_color(palette_id: int, req: ColorCreate, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await palettes_service.add_color(pool, uid, palette_id, req.model_dump())
    except Exception as e:
        raise map_err(e)


@router.patch("/{palette_id}/colors/{color_id}", response_model=ColorOut)
async def update_color(palette_id: int, color_id: int, req: ColorUpdate, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await palettes_service.update_color(pool, uid, color_id, req.model_dump(exclude_unset=True))
    except Exception as e:
        raise map_err(e)


@router.delete("/{palette_id}/colors/{color_id}", response_model=dict)
async def delete_color(palette_id: int, color_id: int, req: ColorDelete, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        await palettes_service.delete_color(pool, uid, color_id, req.replacement_color_id)
        return {"status": "ok"}
    except Exception as e:
        raise map_err(e)
