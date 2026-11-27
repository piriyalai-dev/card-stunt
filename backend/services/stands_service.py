import json

import asyncpg

from core.config import settings
from core.exceptions import ConflictError, NotFoundError, ValidationError
from core.grid import (
    StandGeometry, crop_or_pad_grid, normalize_blocked, validate_blocked_seats, validate_geometry,
)
from core.logger import AuditLogger
from core.rbac import require_permission


def _geometry(row) -> StandGeometry:
    return StandGeometry(
        rows=row["rows"], cols=row["cols"], sub_rows=row["sub_rows"], sub_cols=row["sub_cols"],
        row_direction=row["row_direction"], col_direction=row["col_direction"],
    )


def _out(row) -> dict:
    g = _geometry(row)
    out = dict(row)
    out["grid_width"] = g.grid_width
    out["grid_height"] = g.grid_height
    bs = out.get("blocked_seats")
    out["blocked_seats"] = json.loads(bs) if isinstance(bs, str) else (bs or [])
    return out


async def list_stands(pool: asyncpg.Pool, event_id: int) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM stands WHERE event_id = $1 AND deleted_at IS NULL ORDER BY id", event_id,
        )
    return [_out(r) for r in rows]


async def get_stand(pool: asyncpg.Pool, stand_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM stands WHERE id = $1 AND deleted_at IS NULL", stand_id,
        )
        if not row:
            raise NotFoundError("ไม่พบ stand")
        return _out(row)


async def create_stand(pool: asyncpg.Pool, actor_id: int, event_id: int, data: dict) -> dict:
    g = StandGeometry(
        rows=data["rows"], cols=data["cols"], sub_rows=data["sub_rows"], sub_cols=data["sub_cols"],
        row_direction=data["row_direction"], col_direction=data["col_direction"],
    )
    validate_geometry(g, settings.MAX_TOTAL_CELLS)
    validate_blocked_seats(data.get("blocked_seats", []), g)
    blocked = [{"row": r, "col": c} for r, c in normalize_blocked(data.get("blocked_seats", []))]

    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_STANDS")
            from services.events_service import _bump_version
            await _bump_version(conn, event_id)
            try:
                sid = await conn.fetchval(
                    "INSERT INTO stands (event_id, name, rows, cols, sub_rows, sub_cols,"
                    " seat_aspect_ratio, row_direction, col_direction, row_label_style, col_label_style,"
                    " row_label_prefix, col_label_prefix, blocked_seats)"
                    " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14::jsonb) RETURNING id",
                    event_id, data["name"], data["rows"], data["cols"], data["sub_rows"],
                    data["sub_cols"], data["seat_aspect_ratio"], data["row_direction"],
                    data["col_direction"], data["row_label_style"], data["col_label_style"],
                    data.get("row_label_prefix", ""), data.get("col_label_prefix", ""),
                    json.dumps(blocked),
                )
            except asyncpg.UniqueViolationError:
                raise ConflictError("ชื่อ stand ซ้ำใน event นี้")
            await AuditLogger("stands").log(
                conn, "CREATE_STAND", str(actor_id), "web",
                user_id=actor_id, entity_type="stand", entity_id=str(sid),
                new_values={"event_id": event_id, "name": data["name"]},
            )
            row = await conn.fetchrow("SELECT * FROM stands WHERE id = $1", sid)
    return _out(row)


async def update_stand(pool: asyncpg.Pool, actor_id: int, stand_id: int, data: dict) -> dict:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_STANDS")
            row = await conn.fetchrow(
                "SELECT * FROM stands WHERE id = $1 AND deleted_at IS NULL", stand_id,
            )
            if not row:
                raise NotFoundError("ไม่พบ stand")
            sets, params = [], []
            for col in ("name", "seat_aspect_ratio", "row_direction", "col_direction",
                        "row_label_style", "col_label_style", "row_label_prefix", "col_label_prefix"):
                if data.get(col) is not None:
                    params.append(data[col])
                    sets.append(f"{col} = ${len(params)}")
            if sets:
                sets.append("updated_at = NOW()")
                params.append(stand_id)
                await conn.execute(f"UPDATE stands SET {', '.join(sets)} WHERE id = ${len(params)}", *params)
            await AuditLogger("stands").log(
                conn, "UPDATE_STAND", str(actor_id), "web",
                user_id=actor_id, entity_type="stand", entity_id=str(stand_id),
                old_values={"id": stand_id}, new_values=data,
            )
            updated = await conn.fetchrow("SELECT * FROM stands WHERE id = $1", stand_id)
    return _out(updated)


async def resize_stand(pool: asyncpg.Pool, actor_id: int, stand_id: int, data: dict) -> dict:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_STANDS")
            row = await conn.fetchrow(
                "SELECT * FROM stands WHERE id = $1 AND deleted_at IS NULL", stand_id,
            )
            if not row:
                raise NotFoundError("ไม่พบ stand")
            old_g = _geometry(row)
            new_g = StandGeometry(
                rows=data["rows"], cols=data["cols"],
                sub_rows=data.get("sub_rows") or row["sub_rows"],
                sub_cols=data.get("sub_cols") or row["sub_cols"],
                row_direction=row["row_direction"], col_direction=row["col_direction"],
            )
            validate_geometry(new_g, settings.MAX_TOTAL_CELLS)

            has_grid = bool(await conn.fetchval(
                "SELECT 1 FROM stunts WHERE stand_id = $1 AND deleted_at IS NULL"
                " AND (grid_data_a IS NOT NULL OR grid_data_b IS NOT NULL) LIMIT 1", stand_id,
            ))
            if has_grid and not data.get("allow_crop"):
                raise ConflictError("มี stunt ที่มี grid แล้ว — ต้องระบุ allow_crop=true เพื่อ crop/pad")

            from services.events_service import _bump_version
            await _bump_version(conn, row["event_id"])
            await conn.execute(
                "UPDATE stands SET rows = $1, cols = $2, sub_rows = $3, sub_cols = $4, updated_at = NOW()"
                " WHERE id = $5",
                new_g.rows, new_g.cols, new_g.sub_rows, new_g.sub_cols, stand_id,
            )

            # crop/pad grid ของทุก stunt ให้ตรงขนาดใหม่ (top-left anchor) + snapshot revision
            if has_grid:
                stunts = await conn.fetch(
                    "SELECT id, grid_width, grid_height, grid_data_a, grid_data_b FROM stunts"
                    " WHERE stand_id = $1 AND deleted_at IS NULL", stand_id,
                )
                for st in stunts:
                    a = json.loads(st["grid_data_a"]) if isinstance(st["grid_data_a"], str) else st["grid_data_a"]
                    b = json.loads(st["grid_data_b"]) if isinstance(st["grid_data_b"], str) else st["grid_data_b"]
                    new_a = crop_or_pad_grid(a or [], st["grid_width"], st["grid_height"], new_g.grid_width, new_g.grid_height)
                    new_b = crop_or_pad_grid(b or [], st["grid_width"], st["grid_height"], new_g.grid_width, new_g.grid_height)
                    await conn.execute(
                        "UPDATE stunts SET grid_width = $1, grid_height = $2, grid_data_a = $3::jsonb,"
                        " grid_data_b = $4::jsonb, status = 'ready', updated_at = NOW() WHERE id = $5",
                        new_g.grid_width, new_g.grid_height, json.dumps(new_a), json.dumps(new_b), st["id"],
                    )

            await AuditLogger("stands").log(
                conn, "RESIZE_STAND", str(actor_id), "web",
                user_id=actor_id, entity_type="stand", entity_id=str(stand_id),
                old_values={"rows": old_g.rows, "cols": old_g.cols},
                new_values={"rows": new_g.rows, "cols": new_g.cols, "allow_crop": data.get("allow_crop")},
            )
            updated = await conn.fetchrow("SELECT * FROM stands WHERE id = $1", stand_id)
    return _out(updated)


async def set_blocked(pool: asyncpg.Pool, actor_id: int, stand_id: int, blocked: list) -> dict:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_STANDS")
            row = await conn.fetchrow(
                "SELECT * FROM stands WHERE id = $1 AND deleted_at IS NULL", stand_id,
            )
            if not row:
                raise NotFoundError("ไม่พบ stand")
            g = _geometry(row)
            validate_blocked_seats(blocked, g)
            # กัน blocked ทับ roster ที่มีคนนั่ง
            norm = normalize_blocked(blocked)
            for r, c in norm:
                occupied = await conn.fetchval(
                    "SELECT 1 FROM seat_rosters WHERE stand_id = $1 AND row_index = $2 AND col_index = $3"
                    " AND deleted_at IS NULL LIMIT 1", stand_id, r, c,
                )
                if occupied:
                    raise ConflictError(f"ช่อง ({r},{c}) มีนักเรียนนั่งอยู่แล้ว — ถอดก่อน")
            await conn.execute(
                "UPDATE stands SET blocked_seats = $1::jsonb, updated_at = NOW() WHERE id = $2",
                json.dumps([{"row": r, "col": c} for r, c in norm]), stand_id,
            )
            await AuditLogger("stands").log(
                conn, "SET_BLOCKED", str(actor_id), "web",
                user_id=actor_id, entity_type="stand", entity_id=str(stand_id),
                new_values={"blocked_seats": norm},
            )
            updated = await conn.fetchrow("SELECT * FROM stands WHERE id = $1", stand_id)
    return _out(updated)
