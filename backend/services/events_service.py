import asyncpg

from core.exceptions import ConflictError, NotFoundError, ValidationError
from core.logger import AuditLogger
from core.rbac import require_permission

EVENT_COLUMNS = (
    "id, slug, name, description, event_date, status, version, published_version,"
    " public_access_enabled, palette_a_id, palette_b_id, live_stunt_id, live_is_active,"
    " created_at, updated_at"
)


async def _bump_version(conn: asyncpg.Connection, event_id: int) -> int:
    """bump events.version (ใน transaction เดียวกับ mutation) — ขับ cache/ETag."""
    return await conn.fetchval(
        "UPDATE events SET version = version + 1, updated_at = NOW() WHERE id = $1 RETURNING version",
        event_id,
    )


def _slugify(name: str) -> str:
    import re
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "event"


async def _gen_slug(conn: asyncpg.Connection, base: str) -> str:
    slug = base
    n = 2
    while await conn.fetchval("SELECT 1 FROM events WHERE slug = $1", slug):
        slug = f"{base}-{n}"
        n += 1
    return slug


async def list_events(pool: asyncpg.Pool) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT {EVENT_COLUMNS} FROM events WHERE deleted_at IS NULL ORDER BY id DESC"
        )
        return [dict(r) for r in rows]


async def get_event(pool: asyncpg.Pool, event_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT {EVENT_COLUMNS} FROM events WHERE id = $1 AND deleted_at IS NULL", event_id,
        )
        if not row:
            raise NotFoundError("ไม่พบ event")
        return dict(row)


async def create_event(pool: asyncpg.Pool, actor_id: int, data: dict):
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_EVENTS")
            slug = data.get("slug") or await _gen_slug(conn, _slugify(data["name"]))
            try:
                eid = await conn.fetchval(
                    "INSERT INTO events (slug, name, description, event_date, created_by, updated_by)"
                    " VALUES ($1, $2, $3, $4, $5, $5) RETURNING id",
                    slug, data["name"], data.get("description"), data.get("event_date"), actor_id,
                )
            except asyncpg.UniqueViolationError:
                raise ConflictError("slug นี้ถูกใช้แล้ว")
            await AuditLogger("events").log(
                conn, "CREATE_EVENT", str(actor_id), "web",
                user_id=actor_id, entity_type="event", entity_id=str(eid),
                new_values={"slug": slug, "name": data["name"]},
            )
            return dict(await conn.fetchrow(
                f"SELECT {EVENT_COLUMNS} FROM events WHERE id = $1", eid,
            ))


async def update_event(pool: asyncpg.Pool, actor_id: int, event_id: int, data: dict):
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_EVENTS")
            row = await conn.fetchrow(
                "SELECT id FROM events WHERE id = $1 AND deleted_at IS NULL", event_id,
            )
            if not row:
                raise NotFoundError("ไม่พบ event")
            # palette A/B ต้องเป็นของ event นี้ (หรือ global)
            for pid in (data.get("palette_a_id"), data.get("palette_b_id")):
                if pid is not None:
                    ok = await conn.fetchval(
                        "SELECT 1 FROM palettes WHERE id = $1 AND (event_id = $2 OR event_id IS NULL) AND deleted_at IS NULL",
                        pid, event_id,
                    )
                    if not ok:
                        raise ValidationError("palette ไม่อยู่ใน event นี้")

            sets, params = [], []
            for col in ("name", "description", "event_date", "status",
                        "public_access_enabled", "palette_a_id", "palette_b_id"):
                if data.get(col) is not None:
                    params.append(data[col])
                    sets.append(f"{col} = ${len(params)}")
            if data.get("slug"):
                params.append(data["slug"])
                sets.append(f"slug = ${len(params)}")
            if sets:
                await _bump_version(conn, event_id)
                params.append(event_id)
                await conn.execute(
                    f"UPDATE events SET {', '.join(sets)} WHERE id = ${len(params)}", *params,
                )
            await AuditLogger("events").log(
                conn, "UPDATE_EVENT", str(actor_id), "web",
                user_id=actor_id, entity_type="event", entity_id=str(event_id),
                old_values={"id": event_id}, new_values=data,
            )
            return dict(await conn.fetchrow(
                f"SELECT {EVENT_COLUMNS} FROM events WHERE id = $1", event_id,
            ))


async def delete_event(pool: asyncpg.Pool, actor_id: int, event_id: int):
    """soft delete event + soft-cascade children (DB CASCADE ใช้กับ hard delete เท่านั้น)."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_EVENTS")
            row = await conn.fetchrow(
                "SELECT id FROM events WHERE id = $1 AND deleted_at IS NULL", event_id,
            )
            if not row:
                raise NotFoundError("ไม่พบ event")
            await conn.execute("UPDATE stunts SET deleted_at = NOW() WHERE event_id = $1 AND deleted_at IS NULL", event_id)
            await conn.execute("UPDATE seat_rosters SET deleted_at = NOW() WHERE event_id = $1 AND deleted_at IS NULL", event_id)
            await conn.execute("UPDATE stands SET deleted_at = NOW() WHERE event_id = $1 AND deleted_at IS NULL", event_id)
            await conn.execute("UPDATE palettes SET deleted_at = NOW() WHERE event_id = $1 AND deleted_at IS NULL", event_id)
            # live_queue ไม่มี soft-delete → hard delete
            await conn.execute("DELETE FROM live_queue WHERE event_id = $1", event_id)
            await conn.execute("UPDATE events SET deleted_at = NOW() WHERE id = $1", event_id)
            await AuditLogger("events").log(
                conn, "DELETE_EVENT", str(actor_id), "web",
                user_id=actor_id, entity_type="event", entity_id=str(event_id),
            )


async def duplicate_event(pool: asyncpg.Pool, actor_id: int, event_id: int, data: dict):
    """ลอก event + stands + palettes(+colors) + stunts(+grids) ใน transaction เดียว — ไม่ลอก live/revisions."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_EVENTS")
            src = await conn.fetchrow(
                "SELECT id FROM events WHERE id = $1 AND deleted_at IS NULL", event_id,
            )
            if not src:
                raise NotFoundError("ไม่พบ event")
            slug = data.get("slug") or await _gen_slug(conn, _slugify(data["name"]))
            try:
                new_id = await conn.fetchval(
                    "INSERT INTO events (slug, name, description, event_date, created_by, updated_by)"
                    " VALUES ($1, $2, $3, $4, $5, $5) RETURNING id",
                    slug, data["name"], None, None, actor_id,
                )
            except asyncpg.UniqueViolationError:
                raise ConflictError("slug นี้ถูกใช้แล้ว")

            # stands
            stand_map = {}
            for s in await conn.fetch(
                "SELECT id, name, rows, cols, sub_rows, sub_cols, seat_aspect_ratio, row_direction,"
                " col_direction, row_label_style, col_label_style, row_label_prefix, col_label_prefix,"
                " blocked_seats FROM stands WHERE event_id = $1 AND deleted_at IS NULL ORDER BY id",
                event_id,
            ):
                sid = await conn.fetchval(
                    "INSERT INTO stands (event_id, name, rows, cols, sub_rows, sub_cols,"
                    " seat_aspect_ratio, row_direction, col_direction, row_label_style, col_label_style,"
                    " row_label_prefix, col_label_prefix, blocked_seats)"
                    " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14) RETURNING id",
                    new_id, s["name"], s["rows"], s["cols"], s["sub_rows"], s["sub_cols"],
                    s["seat_aspect_ratio"], s["row_direction"], s["col_direction"],
                    s["row_label_style"], s["col_label_style"], s["row_label_prefix"],
                    s["col_label_prefix"], s["blocked_seats"],
                )
                stand_map[s["id"]] = sid

            # palettes + colors
            palette_map = {}
            for p in await conn.fetch(
                "SELECT id, name, description, is_default FROM palettes"
                " WHERE event_id = $1 AND deleted_at IS NULL ORDER BY id", event_id,
            ):
                pid = await conn.fetchval(
                    "INSERT INTO palettes (event_id, name, description, is_default, created_by)"
                    " VALUES ($1,$2,$3,$4,$5) RETURNING id",
                    new_id, p["name"], p["description"], p["is_default"], actor_id,
                )
                palette_map[p["id"]] = pid
                for c in await conn.fetch(
                    "SELECT code, name_th, hex, text_color, order_index FROM palette_colors"
                    " WHERE palette_id = $1 AND deleted_at IS NULL ORDER BY order_index, id", p["id"],
                ):
                    await conn.execute(
                        "INSERT INTO palette_colors (palette_id, code, name_th, hex, text_color, order_index)"
                        " VALUES ($1,$2,$3,$4,$5,$6)",
                        pid, c["code"], c["name_th"], c["hex"], c["text_color"], c["order_index"],
                    )

            # event palette A/B (remap ผ่าน palette_map)
            src_ev = await conn.fetchrow(
                "SELECT palette_a_id, palette_b_id FROM events WHERE id = $1", event_id,
            )
            await conn.execute(
                "UPDATE events SET palette_a_id = $1, palette_b_id = $2 WHERE id = $3",
                palette_map.get(src_ev["palette_a_id"]), palette_map.get(src_ev["palette_b_id"]), new_id,
            )

            # stunts (side + grid เดียว)
            stunt_map = {}
            for st in await conn.fetch(
                "SELECT id, stand_id, side, code, title, section, notes, order_index,"
                " grid_width, grid_height, grid_data FROM stunts"
                " WHERE event_id = $1 AND deleted_at IS NULL ORDER BY order_index, id", event_id,
            ):
                sid = await conn.fetchval(
                    "INSERT INTO stunts (event_id, stand_id, side, code, title,"
                    " section, notes, order_index, grid_width, grid_height, grid_data,"
                    " created_by, updated_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$12) RETURNING id",
                    new_id, stand_map.get(st["stand_id"]), st["side"], st["code"], st["title"], st["section"],
                    st["notes"], st["order_index"], st["grid_width"], st["grid_height"],
                    st["grid_data"], actor_id,
                )
                stunt_map[st["id"]] = sid

            # rosters — mint access_code ใหม่ (ห้าม copy code เดิมข้ามงาน)
            from services.rosters_service import _mint_access_code
            for r in await conn.fetch(
                "SELECT stand_id, row_index, col_index, row_label, seat_label, student_code, student_name, note"
                " FROM seat_rosters WHERE event_id = $1 AND deleted_at IS NULL ORDER BY id", event_id,
            ):
                access_code = await _mint_access_code(conn, new_id)
                await conn.execute(
                    "INSERT INTO seat_rosters (event_id, stand_id, row_index, col_index, row_label,"
                    " seat_label, student_code, access_code, student_name, note)"
                    " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)",
                    new_id, stand_map.get(r["stand_id"]), r["row_index"], r["col_index"], r["row_label"],
                    r["seat_label"], r["student_code"], access_code, r["student_name"], r["note"],
                )

            # live_queue (remap stunt_id)
            for q in await conn.fetch(
                "SELECT position, stunt_id FROM live_queue WHERE event_id = $1 ORDER BY position", event_id,
            ):
                if q["stunt_id"] in stunt_map:
                    await conn.execute(
                        "INSERT INTO live_queue (event_id, position, stunt_id) VALUES ($1,$2,$3)",
                        new_id, q["position"], stunt_map[q["stunt_id"]],
                    )

            await AuditLogger("events").log(
                conn, "DUPLICATE_EVENT", str(actor_id), "web",
                user_id=actor_id, entity_type="event", entity_id=str(new_id),
                new_values={"slug": slug, "name": data["name"], "from": event_id},
            )
            return dict(await conn.fetchrow(f"SELECT {EVENT_COLUMNS} FROM events WHERE id = $1", new_id))


async def publish_event(pool: asyncpg.Pool, actor_id: int, event_id: int):
    """ตรวจแล้วตั้งทุก stunt เป็น published + bump published_version + reset live."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "PUBLISH_STUNTS")
            row = await conn.fetchrow(
                "SELECT id FROM events WHERE id = $1 AND deleted_at IS NULL", event_id,
            )
            if not row:
                raise NotFoundError("ไม่พบ event")
            has_stand = await conn.fetchval(
                "SELECT 1 FROM stands WHERE event_id = $1 AND deleted_at IS NULL LIMIT 1", event_id,
            )
            has_stunt = await conn.fetchval(
                "SELECT 1 FROM stunts WHERE event_id = $1 AND deleted_at IS NULL LIMIT 1", event_id,
            )
            if not has_stand or not has_stunt:
                raise ValidationError("ต้องมี stand และ stunt อย่างน้อยหนึ่งรายการก่อน publish")

            # seed live_queue จาก stunts (ถ้ายังว่าง) — คิวเริ่มต้น = ลำดับ order_index
            queue_empty = not await conn.fetchval(
                "SELECT 1 FROM live_queue WHERE event_id = $1 LIMIT 1", event_id,
            )
            if queue_empty:
                for i, st in enumerate(await conn.fetch(
                    "SELECT id FROM stunts WHERE event_id = $1 AND deleted_at IS NULL ORDER BY order_index, id",
                    event_id,
                )):
                    await conn.execute(
                        "INSERT INTO live_queue (event_id, position, stunt_id) VALUES ($1,$2,$3)",
                        event_id, i, st["id"],
                    )

            first = await conn.fetchval(
                "SELECT stunt_id FROM live_queue WHERE event_id = $1 ORDER BY position LIMIT 1",
                event_id,
            )
            await conn.execute(
                "UPDATE stunts SET status = 'published' WHERE event_id = $1 AND deleted_at IS NULL",
                event_id,
            )
            await conn.execute(
                "UPDATE events SET published_version = version, published_at = NOW(),"
                " public_access_enabled = TRUE,"
                " live_stunt_id = $2, live_is_active = TRUE, live_updated_at = NOW(), live_updated_by = $3,"
                " updated_at = NOW() WHERE id = $1",
                event_id, first, actor_id,
            )
            await _bump_version(conn, event_id)
            await AuditLogger("events").log(
                conn, "PUBLISH_EVENT", str(actor_id), "web",
                user_id=actor_id, entity_type="event", entity_id=str(event_id),
            )
            return dict(await conn.fetchrow(f"SELECT {EVENT_COLUMNS} FROM events WHERE id = $1", event_id))
