import json

import asyncpg

from core.exceptions import ConflictError, NotFoundError, ValidationError
from core.logger import AuditLogger
from core.rbac import require_permission

PALETTE_COLS = "id, event_id, name, description, is_default, created_at, updated_at"


async def _with_colors(conn: asyncpg.Connection, row) -> dict:
    out = dict(row)
    colors = await conn.fetch(
        "SELECT id, code, name_th, hex, text_color, order_index FROM palette_colors"
        " WHERE palette_id = $1 AND deleted_at IS NULL ORDER BY order_index, id", row["id"],
    )
    out["colors"] = [dict(c) for c in colors]
    return out


async def list_palettes(pool: asyncpg.Pool, event_id: int) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT {PALETTE_COLS} FROM palettes WHERE event_id = $1 AND deleted_at IS NULL ORDER BY id",
            event_id,
        )
        return [await _with_colors(conn, r) for r in rows]


async def get_palette(pool: asyncpg.Pool, palette_id: int) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT {PALETTE_COLS} FROM palettes WHERE id = $1 AND deleted_at IS NULL", palette_id,
        )
        if not row:
            raise NotFoundError("ไม่พบ palette")
        return await _with_colors(conn, row)


async def create_palette(pool: asyncpg.Pool, actor_id: int, event_id: int, data: dict) -> dict:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_PALETTES")
            if data.get("is_default"):
                await conn.execute(
                    "UPDATE palettes SET is_default = FALSE WHERE event_id = $1 AND deleted_at IS NULL",
                    event_id,
                )
            try:
                pid = await conn.fetchval(
                    "INSERT INTO palettes (event_id, name, description, is_default, created_by)"
                    " VALUES ($1,$2,$3,$4,$5) RETURNING id",
                    event_id, data["name"], data.get("description"), data.get("is_default", False), actor_id,
                )
            except asyncpg.UniqueViolationError:
                raise ConflictError("ชื่อ palette ซ้ำใน event นี้")
            for c in data.get("colors", []):
                await conn.execute(
                    "INSERT INTO palette_colors (palette_id, code, name_th, hex, text_color, order_index)"
                    " VALUES ($1,$2,$3,$4,$5,$6)",
                    pid, c["code"], c["name_th"], c["hex"], c.get("text_color", "#FFFFFF"),
                    c.get("order_index", 0),
                )
            await AuditLogger("palettes").log(
                conn, "CREATE_PALETTE", str(actor_id), "web",
                user_id=actor_id, entity_type="palette", entity_id=str(pid),
                new_values={"event_id": event_id, "name": data["name"]},
            )
            row = await conn.fetchrow(f"SELECT {PALETTE_COLS} FROM palettes WHERE id = $1", pid)
    return await get_palette(pool, pid)


async def update_palette(pool: asyncpg.Pool, actor_id: int, palette_id: int, data: dict) -> dict:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_PALETTES")
            row = await conn.fetchrow(
                f"SELECT {PALETTE_COLS} FROM palettes WHERE id = $1 AND deleted_at IS NULL", palette_id,
            )
            if not row:
                raise NotFoundError("ไม่พบ palette")
            if data.get("is_default"):
                await conn.execute(
                    "UPDATE palettes SET is_default = FALSE WHERE event_id = $1 AND deleted_at IS NULL AND id <> $2",
                    row["event_id"], palette_id,
                )
            sets, params = [], []
            for col in ("name", "description", "is_default"):
                if data.get(col) is not None:
                    params.append(data[col])
                    sets.append(f"{col} = ${len(params)}")
            if sets:
                sets.append("updated_at = NOW()")
                params.append(palette_id)
                await conn.execute(f"UPDATE palettes SET {', '.join(sets)} WHERE id = ${len(params)}", *params)
            await AuditLogger("palettes").log(
                conn, "UPDATE_PALETTE", str(actor_id), "web",
                user_id=actor_id, entity_type="palette", entity_id=str(palette_id),
                old_values={"id": palette_id}, new_values=data,
            )
    return await get_palette(pool, palette_id)


async def delete_palette(pool: asyncpg.Pool, actor_id: int, palette_id: int) -> None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_PALETTES")
            row = await conn.fetchrow(
                "SELECT id FROM palettes WHERE id = $1 AND deleted_at IS NULL", palette_id,
            )
            if not row:
                raise NotFoundError("ไม่พบ palette")
            in_use = await conn.fetchval(
                "SELECT 1 FROM events WHERE (palette_a_id = $1 OR palette_b_id = $1) AND deleted_at IS NULL LIMIT 1",
                palette_id,
            )
            if in_use:
                raise ConflictError("palette นี้ถูกใช้เป็นชุดสี A/B ของ event — ลบไม่ได้")
            await conn.execute("UPDATE palette_colors SET deleted_at = NOW() WHERE palette_id = $1", palette_id)
            await conn.execute("UPDATE palettes SET deleted_at = NOW() WHERE id = $1", palette_id)
            await AuditLogger("palettes").log(
                conn, "DELETE_PALETTE", str(actor_id), "web",
                user_id=actor_id, entity_type="palette", entity_id=str(palette_id),
            )


async def add_color(pool: asyncpg.Pool, actor_id: int, palette_id: int, data: dict) -> dict:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_PALETTES")
            await _ensure_palette(conn, palette_id)
            try:
                cid = await conn.fetchval(
                    "INSERT INTO palette_colors (palette_id, code, name_th, hex, text_color, order_index)"
                    " VALUES ($1,$2,$3,$4,$5,$6) RETURNING id",
                    palette_id, data["code"], data["name_th"], data["hex"],
                    data.get("text_color", "#FFFFFF"), data.get("order_index", 0),
                )
            except asyncpg.UniqueViolationError:
                raise ConflictError("code สีซ้ำใน palette นี้")
            await AuditLogger("palettes").log(
                conn, "ADD_COLOR", str(actor_id), "web",
                user_id=actor_id, entity_type="palette_color", entity_id=str(cid),
                new_values={"palette_id": palette_id, "code": data["code"]},
            )
            row = await conn.fetchrow(
                "SELECT id, code, name_th, hex, text_color, order_index FROM palette_colors WHERE id = $1", cid,
            )
    return dict(row)


async def update_color(pool: asyncpg.Pool, actor_id: int, color_id: int, data: dict) -> dict:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_PALETTES")
            row = await conn.fetchrow(
                "SELECT id, palette_id FROM palette_colors WHERE id = $1 AND deleted_at IS NULL", color_id,
            )
            if not row:
                raise NotFoundError("ไม่พบสี")
            sets, params = [], []
            for col in ("code", "name_th", "hex", "text_color", "order_index"):
                if data.get(col) is not None:
                    params.append(data[col])
                    sets.append(f"{col} = ${len(params)}")
            if sets:
                sets.append("updated_at = NOW()")
                params.append(color_id)
                try:
                    await conn.execute(f"UPDATE palette_colors SET {', '.join(sets)} WHERE id = ${len(params)}", *params)
                except asyncpg.UniqueViolationError:
                    raise ConflictError("code สีซ้ำใน palette นี้")
            await AuditLogger("palettes").log(
                conn, "UPDATE_COLOR", str(actor_id), "web",
                user_id=actor_id, entity_type="palette_color", entity_id=str(color_id),
                new_values=data,
            )
            updated = await conn.fetchrow(
                "SELECT id, code, name_th, hex, text_color, order_index FROM palette_colors WHERE id = $1", color_id,
            )
    return dict(updated)


async def delete_color(pool: asyncpg.Pool, actor_id: int, color_id: int, replacement_color_id=None) -> None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_PALETTES")
            row = await conn.fetchrow(
                "SELECT id, palette_id FROM palette_colors WHERE id = $1 AND deleted_at IS NULL", color_id,
            )
            if not row:
                raise NotFoundError("ไม่พบสี")
            used = await conn.fetch(
                "SELECT id, grid_data FROM stunts"
                " WHERE deleted_at IS NULL AND grid_data IS NOT NULL",
            )
            affected = []
            for st in used:
                data = _json(st["grid_data"])
                if color_id in data:
                    affected.append(st["id"])
            if affected and not replacement_color_id:
                raise ConflictError(
                    f"สีนี้ถูกใช้ใน {len(affected)} ฉาก — ต้องระบุ replacement_color_id"
                )
            # เขียนทับ color_id → replacement ในทุก grid ที่ใช้
            for st_id in affected:
                st = await conn.fetchrow(
                    "SELECT grid_data FROM stunts WHERE id = $1", st_id,
                )
                data = _json(st["grid_data"])
                new_data = [replacement_color_id if v == color_id else v for v in data]
                await conn.execute(
                    "UPDATE stunts SET grid_data = $1::jsonb, updated_at = NOW() WHERE id = $2",
                    json.dumps(new_data), st_id,
                )
            await conn.execute("UPDATE palette_colors SET deleted_at = NOW() WHERE id = $1", color_id)
            await AuditLogger("palettes").log(
                conn, "DELETE_COLOR", str(actor_id), "web",
                user_id=actor_id, entity_type="palette_color", entity_id=str(color_id),
                new_values={"replacement_color_id": replacement_color_id, "affected_stunts": affected},
            )


def _json(v):
    return json.loads(v) if isinstance(v, str) else (v or [])


async def _ensure_palette(conn, palette_id):
    if not await conn.fetchval("SELECT 1 FROM palettes WHERE id = $1 AND deleted_at IS NULL", palette_id):
        raise NotFoundError("ไม่พบ palette")
