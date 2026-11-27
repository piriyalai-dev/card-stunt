import asyncpg
from fastapi import APIRouter, Depends, File, Form, UploadFile

from core.dependencies import get_current_user, get_db_pool
from models.event_schemas import EventCreate, EventUpdate, EventOut, DuplicateRequest
from models.stand_schemas import StandCreate, StandUpdate, StandOut
from models.palette_schemas import PaletteCreate, PaletteOut
from models.stunt_schemas import StuntCreate, StuntOut, ReorderRequest
from models.roster_schemas import RosterCreate, RosterOut
from models.export_schemas import ExportCreate, ExportOut
from services import events_service, stands_service, palettes_service, stunts_service, rosters_service, exports_service
from routers._common import map_err, ensure_user

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("", response_model=list[EventOut])
async def list_events(user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    ensure_user(user_ctx)
    return await events_service.list_events(pool)


@router.get("/{event_id}", response_model=EventOut)
async def get_event(event_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    ensure_user(user_ctx)
    try:
        return await events_service.get_event(pool, event_id)
    except Exception as e:
        raise map_err(e)


@router.post("", response_model=EventOut)
async def create_event(req: EventCreate, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await events_service.create_event(pool, uid, req.model_dump())
    except Exception as e:
        raise map_err(e)


@router.patch("/{event_id}", response_model=EventOut)
async def update_event(event_id: int, req: EventUpdate, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await events_service.update_event(pool, uid, event_id, req.model_dump(exclude_unset=True))
    except Exception as e:
        raise map_err(e)


@router.delete("/{event_id}", response_model=dict)
async def delete_event(event_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        await events_service.delete_event(pool, uid, event_id)
        return {"status": "ok"}
    except Exception as e:
        raise map_err(e)


@router.post("/{event_id}/duplicate", response_model=EventOut)
async def duplicate_event(event_id: int, req: DuplicateRequest, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await events_service.duplicate_event(pool, uid, event_id, req.model_dump())
    except Exception as e:
        raise map_err(e)


@router.post("/{event_id}/publish", response_model=EventOut)
async def publish_event(event_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await events_service.publish_event(pool, uid, event_id)
    except Exception as e:
        raise map_err(e)


# ── stands (nested ใต้ event) ──────────────────────────────────────

@router.get("/{event_id}/stands", response_model=list[StandOut])
async def list_stands(event_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    ensure_user(user_ctx)
    return await stands_service.list_stands(pool, event_id)


@router.post("/{event_id}/stands", response_model=StandOut)
async def create_stand(event_id: int, req: StandCreate, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await stands_service.create_stand(pool, uid, event_id, req.model_dump())
    except Exception as e:
        raise map_err(e)


@router.patch("/{event_id}/stands/{stand_id}", response_model=StandOut)
async def update_stand(event_id: int, stand_id: int, req: StandUpdate, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await stands_service.update_stand(pool, uid, stand_id, req.model_dump(exclude_unset=True))
    except Exception as e:
        raise map_err(e)


# ── palettes (nested ใต้ event) ────────────────────────────────────

@router.get("/{event_id}/palettes", response_model=list[PaletteOut])
async def list_palettes(event_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    ensure_user(user_ctx)
    return await palettes_service.list_palettes(pool, event_id)


@router.post("/{event_id}/palettes", response_model=PaletteOut)
async def create_palette(event_id: int, req: PaletteCreate, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await palettes_service.create_palette(pool, uid, event_id, req.model_dump())
    except Exception as e:
        raise map_err(e)


# ── stunts (nested ใต้ event) ──────────────────────────────────────

@router.get("/{event_id}/stunts", response_model=list[StuntOut])
async def list_stunts(event_id: int, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    ensure_user(user_ctx)
    return await stunts_service.list_stunts(pool, event_id)


@router.post("/{event_id}/stunts", response_model=StuntOut)
async def create_stunt(event_id: int, req: StuntCreate, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await stunts_service.create_stunt(pool, uid, event_id, req.model_dump())
    except Exception as e:
        raise map_err(e)


@router.patch("/{event_id}/stunts/reorder", response_model=dict)
async def reorder_stunts(event_id: int, req: ReorderRequest, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        await stunts_service.reorder_stunts(pool, uid, event_id, req.order)
        return {"status": "ok"}
    except Exception as e:
        raise map_err(e)


# ── rosters (nested ใต้ event) ─────────────────────────────────────

@router.get("/{event_id}/rosters", response_model=list[RosterOut])
async def list_rosters(event_id: int, stand_id: int | None = None, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    ensure_user(user_ctx)
    return await rosters_service.list_rosters(pool, event_id, stand_id)


@router.post("/{event_id}/rosters", response_model=RosterOut)
async def create_roster(event_id: int, req: RosterCreate, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await rosters_service.create_roster(pool, uid, event_id, req.model_dump())
    except Exception as e:
        raise map_err(e)


@router.post("/{event_id}/rosters/import", response_model=dict)
async def import_roster(event_id: int, stand_id: int = Form(...), file: UploadFile = File(...),
                        user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    content = await file.read()
    try:
        return await rosters_service.import_roster(pool, uid, event_id, stand_id, content, file.filename or "roster.csv")
    except Exception as e:
        raise map_err(e)


# ── exports (nested ใต้ event) ─────────────────────────────────────

@router.post("/{event_id}/exports", response_model=ExportOut)
async def create_export(event_id: int, req: ExportCreate, user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await exports_service.create_export(pool, uid, event_id, req.model_dump())
    except Exception as e:
        raise map_err(e)
