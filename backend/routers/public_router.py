import asyncio
import json

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from core.config import settings
from core.dependencies import get_db_pool
from core.live_stream import hub
from services import public_service, live_service
from routers._common import map_err

router = APIRouter(prefix="/events", tags=["Public"])


@router.get("/{slug}/meta")
async def meta(slug: str, request: Request, pool: asyncpg.Pool = Depends(get_db_pool)):
    try:
        body, etag, max_age = await public_service.meta(pool, slug)
    except Exception as e:
        raise map_err(e)
    return public_service.respond_cached(body, etag, max_age, request.headers.get("if-none-match"))


@router.get("/{slug}/seat")
async def seat(slug: str, row: int = Query(..., ge=1), col: int = Query(..., ge=1),
               stand_id: int | None = Query(None), request: Request = None,
               pool: asyncpg.Pool = Depends(get_db_pool)):
    try:
        body, etag, max_age = await public_service.seat(pool, slug, row, col, stand_id)
    except Exception as e:
        raise map_err(e)
    return public_service.respond_cached(body, etag, max_age, request.headers.get("if-none-match"))


@router.get("/{slug}/version")
async def version(slug: str, request: Request, pool: asyncpg.Pool = Depends(get_db_pool)):
    try:
        body, etag, max_age = await public_service.version(pool, slug)
    except Exception as e:
        raise map_err(e)
    return public_service.respond_cached(body, etag, max_age, request.headers.get("if-none-match"))


# ── SSE live sync ──────────────────────────────────────────────────

def _sse(event: str | None, data: str) -> str:
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {data}\n\n"


@router.get("/{slug}/live")
async def live(slug: str, request: Request, pool: asyncpg.Pool = Depends(get_db_pool)):
    """SSE: snapshot แรก + poke เมื่อ live state เปลี่ยน (สัญญาณ ไม่ใช่ข้อมูล)."""
    # validate slug ก่อนเปิด stream (404 ได้สะอาด)
    try:
        async with pool.acquire() as conn:
            ev = await public_service._get_public_event(conn, slug)
        event_id = ev["id"]
    except Exception as e:
        raise map_err(e)

    if hub.at_capacity(slug):
        raise HTTPException(status_code=503, detail="เซิร์ฟเวอร์มีผู้รับสตรีมเต็มแล้ว")

    async def event_gen():
        queue = hub.subscribe(slug)
        try:
            state = await live_service.get_live_state(pool, event_id)
            yield _sse("snapshot", json.dumps(state, ensure_ascii=False, default=str))
            while True:
                try:
                    await asyncio.wait_for(queue.get(), timeout=settings.STREAM_HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    if await request.is_disconnected():
                        return
                    continue
                state = await live_service.get_live_state(pool, event_id)
                yield _sse("live", json.dumps(state, ensure_ascii=False, default=str))
        finally:
            hub.unsubscribe(slug, queue)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
