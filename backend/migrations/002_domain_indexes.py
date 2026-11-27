"""
Migration 002 — Indexes + partial unique ของ domain ทั้งหมด (events/stands/palettes/stunts/...)

⚠️ partial unique index (`WHERE deleted_at IS NULL`) กันซ้ำเฉพาะแถว active — soft delete แล้ว
   ใช้ slug/name/code ซ้ำได้ (กฎ backend.md)
⚠️ `lower(name)` บน unique index กันพิมพ์ตัวพิมพ์เล็ก/ใหญ่ซ้ำกัน (idempotent: IF NOT EXISTS)
"""
VERSION = "002_domain_indexes"
DESCRIPTION = "indexes + partial unique ของ events/stands/palettes/stunts/rosters/exports"


async def upgrade(conn) -> None:
    # events
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_events_slug_active ON events(slug) WHERE deleted_at IS NULL"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_status ON events(status) WHERE deleted_at IS NULL"
    )

    # stands
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_stands_event ON stands(event_id) WHERE deleted_at IS NULL"
    )
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_stands_event_name_active"
        " ON stands(event_id, lower(name)) WHERE deleted_at IS NULL"
    )

    # palettes
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_palettes_scope_name_active"
        " ON palettes(COALESCE(event_id, 0), lower(name)) WHERE deleted_at IS NULL"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_palettes_event ON palettes(event_id) WHERE deleted_at IS NULL"
    )

    # palette_colors
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_palette_colors_code_active"
        " ON palette_colors(palette_id, code) WHERE deleted_at IS NULL"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_palette_colors_order"
        " ON palette_colors(palette_id, order_index) WHERE deleted_at IS NULL"
    )

    # stunts
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_stunts_event_code_active"
        " ON stunts(event_id, code) WHERE deleted_at IS NULL"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_stunts_event_order"
        " ON stunts(event_id, order_index) WHERE deleted_at IS NULL"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_stunts_stand ON stunts(stand_id) WHERE deleted_at IS NULL"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_stunts_palette_a ON stunts(palette_a_id) WHERE deleted_at IS NULL"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_stunts_palette_b ON stunts(palette_b_id) WHERE deleted_at IS NULL"
    )

    # stunt_revisions
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_stunt_revisions_no ON stunt_revisions(stunt_id, revision_no)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_stunt_revisions_latest ON stunt_revisions(stunt_id, revision_no DESC)"
    )

    # seat_rosters
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_rosters_seat_active"
        " ON seat_rosters(stand_id, row_index, col_index) WHERE deleted_at IS NULL"
    )
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_rosters_student_active"
        " ON seat_rosters(event_id, student_code) WHERE deleted_at IS NULL AND student_code IS NOT NULL"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rosters_event ON seat_rosters(event_id) WHERE deleted_at IS NULL"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rosters_stand ON seat_rosters(stand_id) WHERE deleted_at IS NULL"
    )

    # export_jobs
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_export_jobs_event_created ON export_jobs(event_id, created_at DESC)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_export_jobs_status ON export_jobs(status) WHERE status IN ('queued','running')"
    )
