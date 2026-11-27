import logging
import uuid
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.init_db import init_db
from core.request_context import set_audit_context, clear_audit_context
from core.live_stream import hub

from routers import (
    auth_router, users_router, events_router, stands_router, palettes_router,
    stunts_router, rosters_router, exports_router, live_router, public_router,
    audit_router, version_router, media_router,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("API_MAIN")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Pixel Stand API...")
    app.state.db_pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=10)
    await init_db(app.state.db_pool)

    from core.seed_users import seed_default_users
    await seed_default_users(app.state.db_pool)

    # 📡 เปิด LISTEN สำหรับ SSE — ต้องเรียกหลัง init_db (trigger สร้างตอน migration)
    #    `start()` ไม่ raise ถ้าต่อไม่ได้ (live sync เป็นของที่ทำให้เร็วขึ้น)
    await hub.start(settings.DATABASE_URL)

    yield

    logger.info("🛑 Shutting down...")
    await hub.stop()
    await app.state.db_pool.close()
    logger.info("✅ Database Pool Closed.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="Pixel Stand API — ระบบแปรอักษรกีฬาสี",
    lifespan=lifespan,
)

# 🌐 CORS — frontend ที่ deploy จริงอยู่คนละ subdomain จาก API (pixel.* → api.*)
# ⇒ ต้องอนุญาต origin จาก config ไม่ใช่ hardcode localhost (ไม่งั้นเบราว์เซอร์บล็อกทุกคำขอ)
_CORS_ORIGINS = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Trace-Id"],
)


def _client_ip(request: Request) -> str:
    """IP จริงของ client — cf-connecting-ip → x-forwarded-for → x-real-ip → client.host"""
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "")


@app.middleware("http")
async def audit_context_middleware(request: Request, call_next):
    """ตั้ง request context ให้ AuditLogger เก็บ ip/UA/endpoint/trace_id อัตโนมัติ."""
    trace_id = str(uuid.uuid4())
    set_audit_context(
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        trace_id=trace_id,
        endpoint=f"{request.method} {request.url.path}",
    )
    try:
        response = await call_next(request)
    finally:
        clear_audit_context()
    response.headers["X-Trace-Id"] = trace_id
    return response


app.include_router(auth_router.router, prefix="/api/v1")
app.include_router(users_router.router, prefix="/api/v1")
app.include_router(events_router.router, prefix="/api/v1")
app.include_router(stands_router.router, prefix="/api/v1")
app.include_router(palettes_router.router, prefix="/api/v1")
app.include_router(stunts_router.router, prefix="/api/v1")
app.include_router(rosters_router.router, prefix="/api/v1")
app.include_router(exports_router.router, prefix="/api/v1")
app.include_router(live_router.router, prefix="/api/v1")
app.include_router(public_router.router, prefix="/api/v1/public")
app.include_router(media_router.router, prefix="/api/v1")
app.include_router(audit_router.router, prefix="/api/v1")
app.include_router(version_router.router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    try:
        async with app.state.db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception:
        return {"status": "error", "database": "disconnected"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
