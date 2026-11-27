import logging
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.init_db import init_db
from routers import auth_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("API_MAIN")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Pixel Stand API...")
    app.state.db_pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=10)
    await init_db(app.state.db_pool)

    from core.seed_users import seed_default_users
    await seed_default_users(app.state.db_pool)

    yield

    await app.state.db_pool.close()
    logger.info("✅ Database Pool Closed.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="Pixel Stand API — ระบบแปรอักษรกีฬาสี",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/api")


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
