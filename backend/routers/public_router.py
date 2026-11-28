import asyncio
import json

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.config import settings
from core.dependencies import get_db_pool
from core.live_stream import hub
from core.ratelimit import check_rate_limit
from routers._common import map_err
from services import public_service, live_service

router = APIRouter(prefix="/events", tags=["Public"])


class ClaimRequest(BaseModel):
    access_code: str


def _ip(request: Request) -> str:
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")


@router.get("/{slug}/meta")
async def meta(slug: str, request: Request, pool: asyncpg.Pool = Depends(get_db_pool)):
    try:
        body, etag, max_age = await public_service.meta(pool, slug)
    except Exception as e:
        raise map_err(e)
    return public_service.respond_cached(body, etag, max_age, request.headers.get("if-none-match"))


@router.post("/{slug}/claim")
async def claim(slug: str, req: ClaimRequest, request: Request, pool: asyncpg.Pool = Depends(get_db_pool)):
    """ล็อกอินด้วยรหัสสุ่ม (พิมพ์แจกนักเรียน) — rate-limit ต่อ IP กัน brute-force."""
    try:
        await check_rate_limit(
            [f"pixelstand:ratelimit:claim:ip:{_ip(request)}"],
            settings.CLAIM_RATE_LIMIT_MAX, settings.CLAIM_RATE_LIMIT_WINDOW_SECONDS,
        )
        return await public_service.claim(pool, slug, req.access_code)
    except Exception as e:
        raise map_err(e)


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
