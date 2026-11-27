import asyncio
import logging
import os
import sys

import asyncpg

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("API_INIT_DB")


async def init_db(pool: asyncpg.Pool):
    """สร้างตารางหลัก (users) + รัน migrations — เรียกจาก main.py (startup) และ run_setup (CLI).

    card-stunt เก็บ `role` ตรงบน `users` (admin / designer / staff) — ไม่มีตาราง students/rooms
    แบบ prsc_portal (3 บทบาท ไม่มีห้อง/ระดับชั้น)
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    display_name TEXT,
                    role TEXT NOT NULL DEFAULT 'staff',
                    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMPTZ
                );
            """)

    # รัน migration (สร้าง schema_migrations + ใช้ NNN_*.py)
    from core.migrations import run_migrations
    await run_migrations(pool)

    logger.info("✅ Pixel Stand Database Initialized Successfully!")


async def run_setup():
    pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=5)
    try:
        await init_db(pool)
        logger.info("✨ Database Setup Process Finished!")
    finally:
        await pool.close()


if __name__ == "__main__":
    if not settings.DATABASE_URL:
        logger.error("❌ DATABASE_URL not found in .env file!")
        sys.exit(1)
    asyncio.run(run_setup())
