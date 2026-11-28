"""
006 — ย้ายจาก "1 ฉาก = 2 หน้า (A+B)" → "1 ฉาก = 1 ภาพ + side A/B" + คิวแสดง + รหัสนักเรียน

- `stunts.side` ('A'|'B') + `grid_data` เดียว (เดิม grid_data_a/grid_data_b)
- `events.palette_a_id`/`palette_b_id` — ชุดสีของด้าน A/B ระดับงาน (เดิมอยู่ที่ stunts)
- `seat_rosters.access_code` — รหัสล็อกอินสุ่มพิมพ์แจกนักเรียน (ล็อกดาวน์ viewer)
- `live_queue` — คิวแสดงแยกจาก order_index (จัดล่วงหน้า/แทรกได้)
- DROP `events.roster_lookup_enabled` (หมดหน้าที่ — ค้นหาเลข ปชช. ถูกปิด)

⚠️ เขียนแบบ idempotent (`ADD/DROP COLUMN IF EXISTS` + `DO $$` guard rename) เพราะ
   `init_db` สร้าง schema ฐานแล้วรัน migration ทั้งหมด ทั้ง fresh DB และ DB เดิม
⚠️ data เดิม (ยังไม่ deploy) → ฉากเก่า treat เป็น side 'A' + ใช้ grid_data_a ของมัน
⚠️ FK events.palette_* ประกาศที่ท้ายสุด (events ถูกสร้างก่อน palettes ใน init_db)
"""
VERSION = "006_single_side_queue"
DESCRIPTION = "stunts.side + grid_data เดียว, event palette A/B, access_code, live_queue"


async def upgrade(conn) -> None:
    # ── 1. events: เพิ่ม palette A/B (plain INT ก่อน — FK เพิ่มทีหลัง) ──
    await conn.execute("ALTER TABLE events ADD COLUMN IF NOT EXISTS palette_a_id INT")
    await conn.execute("ALTER TABLE events ADD COLUMN IF NOT EXISTS palette_b_id INT")

    # ── 2. backfill event palette จาก stunt เดิม (ก่อน drop คอลัมน์ stunt) ──
    await conn.execute("""
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'stunts' AND column_name = 'palette_a_id'
          ) THEN
            UPDATE events e SET
              palette_a_id = (
                SELECT palette_a_id FROM stunts
                WHERE event_id = e.id AND palette_a_id IS NOT NULL AND deleted_at IS NULL
                ORDER BY id LIMIT 1
              ),
              palette_b_id = (
                SELECT palette_b_id FROM stunts
                WHERE event_id = e.id AND palette_b_id IS NOT NULL AND deleted_at IS NULL
                ORDER BY id LIMIT 1
              )
            WHERE e.palette_a_id IS NULL AND e.palette_b_id IS NULL;
          END IF;
        END $$;
    """)

    # ── 3. stunts.side ──
    await conn.execute(
        "ALTER TABLE stunts ADD COLUMN IF NOT EXISTS side TEXT NOT NULL DEFAULT 'A'"
    )

    # ── 4. stunts: rename grid_data_a → grid_data (guard) ──
    await conn.execute("""
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'stunts' AND column_name = 'grid_data_a'
          ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'stunts' AND column_name = 'grid_data'
          ) THEN
            ALTER TABLE stunts RENAME COLUMN grid_data_a TO grid_data;
          END IF;
        END $$;
    """)

    # ── 5. stunts: drop หน้า B + palette ids ──
    await conn.execute("ALTER TABLE stunts DROP COLUMN IF EXISTS grid_data_b")
    await conn.execute("ALTER TABLE stunts DROP COLUMN IF EXISTS palette_a_id")
    await conn.execute("ALTER TABLE stunts DROP COLUMN IF EXISTS palette_b_id")

    # ── 6. stunt_revisions: rename + drop ──
    await conn.execute("""
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'stunt_revisions' AND column_name = 'grid_data_a'
          ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'stunt_revisions' AND column_name = 'grid_data'
          ) THEN
            ALTER TABLE stunt_revisions RENAME COLUMN grid_data_a TO grid_data;
          END IF;
        END $$;
    """)
    await conn.execute("ALTER TABLE stunt_revisions DROP COLUMN IF EXISTS grid_data_b")
    await conn.execute("ALTER TABLE stunt_revisions DROP COLUMN IF EXISTS palette_a_id")
    await conn.execute("ALTER TABLE stunt_revisions DROP COLUMN IF EXISTS palette_b_id")

    # ── 7. seat_rosters.access_code + unique ──
    await conn.execute("ALTER TABLE seat_rosters ADD COLUMN IF NOT EXISTS access_code TEXT")
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_rosters_access_active"
        " ON seat_rosters(event_id, access_code)"
        " WHERE deleted_at IS NULL AND access_code IS NOT NULL"
    )

    # ── 8. live_queue (คิวแสดง) ──
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS live_queue (
            id BIGSERIAL PRIMARY KEY,
            event_id INT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            position INT NOT NULL,
            stunt_id INT NOT NULL REFERENCES stunts(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_live_queue_event_position UNIQUE (event_id, position),
            CONSTRAINT uq_live_queue_event_stunt UNIQUE (event_id, stunt_id)
        )
    """)
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_live_queue_event_position ON live_queue(event_id, position)"
    )

    # ── 9. drop roster_lookup_enabled (ค้นหาเลข ปชช. ถูกปิดแล้ว) ──
    await conn.execute("ALTER TABLE events DROP COLUMN IF EXISTS roster_lookup_enabled")

    # ── 10. FK events.palette_* → palettes (guarded — ไม่มี ADD CONSTRAINT IF NOT EXISTS) ──
    await conn.execute("""
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_events_palette_a') THEN
            ALTER TABLE events ADD CONSTRAINT fk_events_palette_a
              FOREIGN KEY (palette_a_id) REFERENCES palettes(id) ON DELETE SET NULL;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_events_palette_b') THEN
            ALTER TABLE events ADD CONSTRAINT fk_events_palette_b
              FOREIGN KEY (palette_b_id) REFERENCES palettes(id) ON DELETE SET NULL;
          END IF;
        END $$;
    """)
