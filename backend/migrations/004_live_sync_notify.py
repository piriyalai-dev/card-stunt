"""
004 — `pg_notify` ตอน live state เปลี่ยน ⇒ viewer กลางสนามอัปเดตทันที (SSE)

⭐ ทำไม `pg_notify` ไม่ใช่ publish จาก Python
   advance/update live อยู่ใน transaction ของ caller ⇒ ถ้า publish จาก Python จะยิง
   **ก่อน** commit ⇒ viewer เห็น "เปลี่ยนฉาก" ของ transaction ที่ถูก rollback ไปแล้ว
   `pg_notify` ยิงตอน COMMIT เท่านั้น ⇒ rollback = ไม่มี event (มีเทสต์พิสูจน์)

⚠️ payload มีแค่ `slug` (+ version/stunt id) — ไม่มีเนื้อหาฉาก:
   1. ความปลอดภัย — payload วิ่งผ่านทุกโปรเซสที่ LISTEN ⇒ เนื้อหาฉากไม่ควรรั่ว
   2. ขนาด — payload ต้องเล็ก (pg_notify จำกัด 8,000 byte)
   ⇒ client ใช้ payload เป็น "สัญญาณให้ไปอ่านสถานะจริงจาก DB" (source of truth เดียว = events)

⚠️ trigger ยิงเฉพาะเมื่อ `live_stunt_id`/`live_is_active` เปลี่ยน (UPDATE OF) — ไม่ใช่ทุก
   การแก้ event · `PERFORM` ไม่ใช่ `SELECT` (pg_notify คืน void) · `DROP TRIGGER IF EXISTS`
   จำเป็นเพราะ `CREATE TRIGGER` ไม่มี IF NOT EXISTS

📌 ไม่ mirror ลง init_db.py — function/trigger ต้องมีนิยามเดียว (กฎเดียวกับ prsc 020)
"""
VERSION = "004_live_sync_notify"
DESCRIPTION = "trigger AFTER UPDATE OF live_stunt_id/live_is_active → pg_notify('pixelstand_live')"


async def upgrade(conn) -> None:
    await conn.execute("""
        CREATE OR REPLACE FUNCTION pixelstand_live_notify() RETURNS trigger AS $$
        BEGIN
            PERFORM pg_notify(
                'pixelstand_live',
                json_build_object(
                    'slug', NEW.slug,
                    'live_stunt_id', NEW.live_stunt_id,
                    'live_is_active', NEW.live_is_active,
                    'version', NEW.version
                )::text
            );
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    await conn.execute("DROP TRIGGER IF EXISTS trg_pixelstand_live_notify ON events;")
    await conn.execute("""
        CREATE TRIGGER trg_pixelstand_live_notify
            AFTER UPDATE OF live_stunt_id, live_is_active ON events
            FOR EACH ROW EXECUTE FUNCTION pixelstand_live_notify();
    """)
