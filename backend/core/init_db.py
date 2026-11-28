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
    """สร้างตารางหลักทั้งหมด + รัน migrations — เรียกจาก main.py (startup) และ run_setup (CLI).

    ลำดับ DDL เรียงตาม FK: users → events → stands → palettes → palette_colors
    → stunts → stunt_revisions → seat_rosters → export_jobs → audit_logs

    ⚠️ source of truth = ไฟล์นี้ · behavior/trigger อยู่ที่ migration เท่านั้น (กฎ backend.md)
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            # ── 1. users ────────────────────────────────────────────
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    display_name TEXT,
                    role TEXT NOT NULL DEFAULT 'staff',
                    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
                    token_version INT NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMPTZ
                );
            """)

            # ── 2. events ───────────────────────────────────────────
            #   version = bump ทุก mutation ของ subtree (ขับ cache/ETag)
            #   live_stunt_id ตั้งใจ **ไม่มี FK** (circular กับ stunts) — service validate
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    slug TEXT NOT NULL CHECK (slug ~ '^[a-z0-9][a-z0-9-]{0,79}$'),
                    name TEXT NOT NULL,
                    description TEXT,
                    event_date DATE,
                    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','archived')),
                    version INT NOT NULL DEFAULT 1,
                    published_version INT NOT NULL DEFAULT 0,
                    published_at TIMESTAMPTZ,
                    public_access_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    roster_lookup_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    live_stunt_id INT,
                    live_is_active BOOLEAN NOT NULL DEFAULT FALSE,
                    live_updated_at TIMESTAMPTZ,
                    live_updated_by INT REFERENCES users(id) ON DELETE SET NULL,
                    created_by INT REFERENCES users(id) ON DELETE SET NULL,
                    updated_by INT REFERENCES users(id) ON DELETE SET NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMPTZ
                );
            """)

            # ── 3. stands ───────────────────────────────────────────
            #   UNIQUE(id, event_id) เป็น target ของ composite FK จาก stunts/rosters
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS stands (
                    id SERIAL PRIMARY KEY,
                    event_id INT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    rows INT NOT NULL CHECK (rows > 0),
                    cols INT NOT NULL CHECK (cols > 0),
                    sub_rows INT NOT NULL DEFAULT 5 CHECK (sub_rows BETWEEN 1 AND 16),
                    sub_cols INT NOT NULL DEFAULT 5 CHECK (sub_cols BETWEEN 1 AND 16),
                    seat_aspect_ratio DOUBLE PRECISION NOT NULL DEFAULT 1.0 CHECK (seat_aspect_ratio BETWEEN 0.4 AND 2.5),
                    row_direction TEXT NOT NULL DEFAULT 'bottom_to_top' CHECK (row_direction IN ('bottom_to_top','top_to_bottom')),
                    col_direction TEXT NOT NULL DEFAULT 'left_to_right' CHECK (col_direction IN ('left_to_right','right_to_left')),
                    row_label_style TEXT NOT NULL DEFAULT 'alpha' CHECK (row_label_style IN ('numeric','alpha')),
                    col_label_style TEXT NOT NULL DEFAULT 'numeric' CHECK (col_label_style IN ('numeric','alpha')),
                    row_label_prefix TEXT NOT NULL DEFAULT '',
                    col_label_prefix TEXT NOT NULL DEFAULT '',
                    blocked_seats JSONB NOT NULL DEFAULT '[]',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMPTZ,
                    CONSTRAINT uq_stands_id_event UNIQUE (id, event_id)
                );
            """)

            # ── 4. palettes ─────────────────────────────────────────
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS palettes (
                    id SERIAL PRIMARY KEY,
                    event_id INT REFERENCES events(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    description TEXT,
                    is_default BOOLEAN NOT NULL DEFAULT FALSE,
                    created_by INT REFERENCES users(id) ON DELETE SET NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMPTZ
                );
            """)

            # ── 5. palette_colors ───────────────────────────────────
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS palette_colors (
                    id SERIAL PRIMARY KEY,
                    palette_id INT NOT NULL REFERENCES palettes(id) ON DELETE CASCADE,
                    code TEXT NOT NULL,
                    name_th TEXT NOT NULL,
                    hex TEXT NOT NULL CHECK (hex ~ '^#[0-9A-Fa-f]{6}$'),
                    text_color TEXT NOT NULL DEFAULT '#FFFFFF' CHECK (text_color ~ '^#[0-9A-Fa-f]{6}$'),
                    order_index INT NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMPTZ
                );
            """)

            # ── 6. stunts (2 หน้า: palette_a/grid_data_a + palette_b/grid_data_b) ──
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS stunts (
                    id SERIAL PRIMARY KEY,
                    event_id INT NOT NULL,
                    stand_id INT NOT NULL,
                    palette_a_id INT REFERENCES palettes(id) ON DELETE SET NULL,
                    palette_b_id INT REFERENCES palettes(id) ON DELETE SET NULL,
                    code TEXT NOT NULL,
                    title TEXT NOT NULL,
                    section TEXT,
                    notes TEXT,
                    order_index INT NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','ready','published')),
                    grid_width INT NOT NULL,
                    grid_height INT NOT NULL,
                    grid_data_a JSONB,
                    grid_data_b JSONB,
                    reference_image_path TEXT,
                    reference_transform JSONB,
                    thumbnail_path TEXT,
                    created_by INT REFERENCES users(id) ON DELETE SET NULL,
                    updated_by INT REFERENCES users(id) ON DELETE SET NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMPTZ,
                    CONSTRAINT fk_stunts_stand_event FOREIGN KEY (stand_id, event_id)
                        REFERENCES stands(id, event_id) ON DELETE CASCADE
                );
            """)

            # ── 7. stunt_revisions ──────────────────────────────────
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS stunt_revisions (
                    id BIGSERIAL PRIMARY KEY,
                    stunt_id INT NOT NULL REFERENCES stunts(id) ON DELETE CASCADE,
                    revision_no INT NOT NULL CHECK (revision_no > 0),
                    grid_width INT NOT NULL,
                    grid_height INT NOT NULL,
                    grid_data_a JSONB,
                    grid_data_b JSONB,
                    palette_a_id INT REFERENCES palettes(id) ON DELETE SET NULL,
                    palette_b_id INT REFERENCES palettes(id) ON DELETE SET NULL,
                    note TEXT,
                    created_by INT REFERENCES users(id) ON DELETE SET NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # ── 8. seat_rosters ─────────────────────────────────────
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS seat_rosters (
                    id SERIAL PRIMARY KEY,
                    event_id INT NOT NULL,
                    stand_id INT NOT NULL,
                    row_index INT NOT NULL CHECK (row_index >= 0),
                    col_index INT NOT NULL CHECK (col_index >= 0),
                    row_label TEXT,
                    seat_label TEXT,
                    student_code TEXT,
                    student_name TEXT NOT NULL,
                    note TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMPTZ,
                    CONSTRAINT fk_rosters_stand_event FOREIGN KEY (stand_id, event_id)
                        REFERENCES stands(id, event_id) ON DELETE CASCADE
                );
            """)

            # ── 9. export_jobs (ARQ/file generation = Phase 5) ─────
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS export_jobs (
                    id SERIAL PRIMARY KEY,
                    event_id INT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                    stand_id INT REFERENCES stands(id) ON DELETE SET NULL,
                    format TEXT NOT NULL CHECK (format IN ('pdf','csv','zip')),
                    scope TEXT NOT NULL DEFAULT 'event',
                    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','done','failed')),
                    file_path TEXT,
                    error TEXT,
                    requested_by INT REFERENCES users(id) ON DELETE SET NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMPTZ,
                    deleted_at TIMESTAMPTZ
                );
            """)

            # ── 10. audit_logs (ทุกคอลัมน์ NOT NULL, no FK) ─────────
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id BIGSERIAL PRIMARY KEY,
                    trace_id VARCHAR(64) NOT NULL DEFAULT '-',
                    user_id INT NOT NULL DEFAULT -1,
                    actor_identifier VARCHAR(100) NOT NULL DEFAULT '-',
                    client_source VARCHAR(20) NOT NULL DEFAULT '-',
                    service_name VARCHAR(50) NOT NULL DEFAULT '-',
                    action VARCHAR(50) NOT NULL DEFAULT '-',
                    entity_type VARCHAR(50) NOT NULL DEFAULT '-',
                    entity_id VARCHAR(50) NOT NULL DEFAULT '-',
                    status VARCHAR(20) NOT NULL DEFAULT 'success' CHECK (status IN ('success','error','partial')),
                    error_detail TEXT NOT NULL DEFAULT '-',
                    old_values JSONB NOT NULL DEFAULT '{}',
                    new_values JSONB NOT NULL DEFAULT '{}',
                    endpoint_or_command TEXT NOT NULL DEFAULT '-',
                    ip_address VARCHAR(45) NOT NULL DEFAULT '-',
                    user_agent TEXT NOT NULL DEFAULT '-',
                    execution_time_ms INT NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
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
