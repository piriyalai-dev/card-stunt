import json

import asyncpg

from core.config import settings
from core.exceptions import ConflictError, NotFoundError, ValidationError
from core.logger import AuditLogger
from core.rbac import require_permission

STUNT_COLS = (
    "id, event_id, stand_id, palette_a_id, palette_b_id, code, title, section, notes, order_index,"
    " status, grid_width, grid_height, reference_image_path, reference_transform, thumbnail_path,"
    " created_at, updated_at"
)


def _json(v):
    return json.loads(v) if isinstance(v, str) else v


def _out(d):
    """parse JSONB fields (reference_transform) ก่อนส่งกลับ response model."""
    rt = d.get("reference_transform")
    if isinstance(rt, str):
        d["reference_transform"] = json.loads(rt)
    return d


async def list_stunts(pool: asyncpg.Pool, event_id: int) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT {STUNT_COLS} FROM stunts WHERE event_id = $1 AND deleted_at IS NULL ORDER BY order_index, id",
            event_id,
        )
        return [_out(dict(r)) for r in rows]


async def get_stunt(pool: asyncpg.Pool, stunt_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT {STUNT_COLS} FROM stunts WHERE id = $1 AND deleted_at IS NULL", stunt_id,
        )
        if not row:
            raise NotFoundError("ไม่พบ stunt")
        return _out(dict(row))


async def create_stunt(pool: asyncpg.Pool, actor_id: int, event_id: int, data: dict) -> dict:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_STUNTS")
            stand_id = data.get("stand_id")
            if not stand_id:
                stand_id = await conn.fetchval(
                    "SELECT id FROM stands WHERE event_id = $1 AND deleted_at IS NULL ORDER BY id LIMIT 1",
                    event_id,
                )
                if not stand_id:
                    raise ValidationError("ต้องสร้าง stand ก่อน")
            stand = await conn.fetchrow(
                "SELECT rows, cols, sub_rows, sub_cols FROM stands WHERE id = $1 AND event_id = $2 AND deleted_at IS NULL",
                stand_id, event_id,
            )
            if not stand:
                raise ValidationError("stand ไม่อยู่ใน event นี้")
            gw = stand["cols"] * stand["sub_cols"]
            gh = stand["rows"] * stand["sub_rows"]

            # validate palette อยู่ใน event
            for pid in (data.get("palette_a_id"), data.get("palette_b_id")):
                if pid:
                    ok = await conn.fetchval(
                        "SELECT 1 FROM palettes WHERE id = $1 AND (event_id = $2 OR event_id IS NULL) AND deleted_at IS NULL",
                        pid, event_id,
                    )
                    if not ok:
                        raise ValidationError("palette ไม่อยู่ใน event นี้")

            try:
                sid = await conn.fetchval(
                    "INSERT INTO stunts (event_id, stand_id, palette_a_id, palette_b_id, code, title,"
                    " section, notes, order_index, grid_width, grid_height, created_by, updated_by)"
                    " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$12) RETURNING id",
                    event_id, stand_id, data.get("palette_a_id"), data.get("palette_b_id"),
                    data["code"], data["title"], data.get("section"), data.get("notes"),
                    data.get("order_index", 0), gw, gh, actor_id,
                )
            except asyncpg.UniqueViolationError:
                raise ConflictError("code ซ้ำใน event นี้")

            await AuditLogger("stunts").log(
                conn, "CREATE_STUNT", str(actor_id), "web",
                user_id=actor_id, entity_type="stunt", entity_id=str(sid),
                new_values={"event_id": event_id, "code": data["code"]},
            )
            return _out(dict(await conn.fetchrow(f"SELECT {STUNT_COLS} FROM stunts WHERE id = $1", sid)))


async def update_stunt(pool: asyncpg.Pool, actor_id: int, stunt_id: int, data: dict) -> dict:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_STUNTS")
            row = await conn.fetchrow(
                f"SELECT {STUNT_COLS} FROM stunts WHERE id = $1 AND deleted_at IS NULL", stunt_id,
            )
            if not row:
                raise NotFoundError("ไม่พบ stunt")
            sets, params = [], []
            for col in ("code", "title", "section", "notes", "order_index", "status",
                        "palette_a_id", "palette_b_id"):
                if data.get(col) is not None:
                    params.append(data[col])
                    sets.append(f"{col} = ${len(params)}")
            if data.get("reference_transform") is not None:
                params.append(json.dumps(data["reference_transform"]))
                sets.append(f"reference_transform = ${len(params)}::jsonb")
            if sets:
                from services.events_service import _bump_version
                await _bump_version(conn, row["event_id"])
                sets.append("updated_by = $" + str(len(params) + 1))
                params.append(actor_id)
                sets.append("updated_at = NOW()")
                params.append(stunt_id)
                await conn.execute(f"UPDATE stunts SET {', '.join(sets)} WHERE id = ${len(params)}", *params)
            await AuditLogger("stunts").log(
                conn, "UPDATE_STUNT", str(actor_id), "web",
                user_id=actor_id, entity_type="stunt", entity_id=str(stunt_id),
                old_values={"id": stunt_id}, new_values=data,
            )
            return _out(dict(await conn.fetchrow(f"SELECT {STUNT_COLS} FROM stunts WHERE id = $1", stunt_id)))


async def delete_stunt(pool: asyncpg.Pool, actor_id: int, stunt_id: int) -> None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_STUNTS")
            row = await conn.fetchrow(
                "SELECT id, event_id FROM stunts WHERE id = $1 AND deleted_at IS NULL", stunt_id,
            )
            if not row:
                raise NotFoundError("ไม่พบ stunt")
            from services.events_service import _bump_version
            await _bump_version(conn, row["event_id"])
            await conn.execute("UPDATE stunts SET deleted_at = NOW() WHERE id = $1", stunt_id)
            await AuditLogger("stunts").log(
                conn, "DELETE_STUNT", str(actor_id), "web",
                user_id=actor_id, entity_type="stunt", entity_id=str(stunt_id),
            )


async def reorder_stunts(pool: asyncpg.Pool, actor_id: int, event_id: int, order: list) -> None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_STUNTS")
            existing = {
                r["id"] for r in await conn.fetch(
                    "SELECT id FROM stunts WHERE event_id = $1 AND deleted_at IS NULL", event_id,
                )
            }
            if set(order) != existing:
                raise ValidationError("order ต้องครอบคลุมทุก stunt ใน event นี้แบบไม่ซ้ำ")
            for i, sid in enumerate(order):
                await conn.execute(
                    "UPDATE stunts SET order_index = $1, updated_at = NOW() WHERE id = $2", i, sid,
                )
            await AuditLogger("stunts").log(
                conn, "REORDER_STUNTS", str(actor_id), "web",
                user_id=actor_id, entity_type="event", entity_id=str(event_id),
                new_values={"order": order},
            )


async def update_grid(pool: asyncpg.Pool, actor_id: int, stunt_id: int, data: dict) -> dict:
    """ตรวจ + บันทึก grid ใหม่ + snapshot revision (ใน transaction เดียว)."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_STUNTS")
            # fetch พร้อม grid_data เดิม (STUNT_COLS ไม่มี grid_data — ต้องดึงแยกสำหรับ snapshot)
            row = await conn.fetchrow(
                "SELECT id, event_id, palette_a_id, palette_b_id, grid_width, grid_height, grid_data_a, grid_data_b"
                " FROM stunts WHERE id = $1 AND deleted_at IS NULL", stunt_id,
            )
            if not row:
                raise NotFoundError("ไม่พบ stunt")

            allowed_a = await _color_ids(conn, row["palette_a_id"])
            allowed_b = await _color_ids(conn, row["palette_b_id"])
            a = data.get("grid_data_a")
            b = data.get("grid_data_b")
            if a is None and b is None:
                raise ValidationError("ต้องระบุ grid_data_a หรือ grid_data_b")
            _validate(a, row["grid_width"], row["grid_height"], allowed_a)
            _validate(b, row["grid_width"], row["grid_height"], allowed_b)

            from services.events_service import _bump_version
            await _bump_version(conn, row["event_id"])

            if a is not None:
                await conn.execute(
                    "UPDATE stunts SET grid_data_a = $1::jsonb, updated_at = NOW(), updated_by = $2 WHERE id = $3",
                    json.dumps(a), actor_id, stunt_id,
                )
            if b is not None:
                await conn.execute(
                    "UPDATE stunts SET grid_data_b = $1::jsonb, updated_at = NOW(), updated_by = $2 WHERE id = $3",
                    json.dumps(b), actor_id, stunt_id,
                )
            # grid ถูกแก้ → ต้อง re-publish ⇒ status กลับ ready
            await conn.execute(
                "UPDATE stunts SET status = 'ready' WHERE id = $1 AND status = 'published'", stunt_id,
            )

            await _snapshot_revision(conn, stunt_id, actor_id, data.get("note"), row)

            await AuditLogger("stunts").log(
                conn, "UPDATE_GRID", str(actor_id), "web",
                user_id=actor_id, entity_type="stunt", entity_id=str(stunt_id),
                new_values={"grid_width": row["grid_width"], "grid_height": row["grid_height"]},
            )
            return _out(dict(await conn.fetchrow(f"SELECT {STUNT_COLS} FROM stunts WHERE id = $1", stunt_id)))


def _validate(grid, w, h, allowed):
    if grid is None:
        return
    if not isinstance(grid, list):
        raise ValidationError("grid_data ต้องเป็น array")
    if len(grid) != w * h:
        raise ValidationError(f"grid ยาว {len(grid)} แต่ควรเป็น {w * h}")
    allowed = set(allowed or [])
    for v in grid:
        if v is not None and int(v) not in allowed:
            raise ValidationError(f"grid มีสี {v} ที่ไม่อยู่ใน palette")


async def _color_ids(conn, palette_id):
    if not palette_id:
        return []
    return [
        r["id"] for r in await conn.fetch(
            "SELECT id FROM palette_colors WHERE palette_id = $1 AND deleted_at IS NULL", palette_id,
        )
    ]


async def _snapshot_revision(conn, stunt_id, actor_id, note, row):
    next_no = await conn.fetchval(
        "SELECT COALESCE(MAX(revision_no), 0) + 1 FROM stunt_revisions WHERE stunt_id = $1", stunt_id,
    )
    await conn.execute(
        "INSERT INTO stunt_revisions (stunt_id, revision_no, grid_width, grid_height, grid_data_a,"
        " grid_data_b, palette_a_id, palette_b_id, note, created_by)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)",
        stunt_id, next_no, row["grid_width"], row["grid_height"],
        row["grid_data_a"], row["grid_data_b"], row["palette_a_id"], row["palette_b_id"],
        note, actor_id,
    )
    # prune เก็บแค่ REVISION_RETENTION ล่าสุด
    await conn.execute(
        "DELETE FROM stunt_revisions WHERE stunt_id = $1 AND revision_no <= ("
        " SELECT COALESCE(MAX(revision_no), 0) - $2 FROM stunt_revisions WHERE stunt_id = $1"
        ")",
        stunt_id, settings.REVISION_RETENTION,
    )


async def list_revisions(pool: asyncpg.Pool, stunt_id: int) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, revision_no, grid_width, grid_height, note, created_by, created_at"
            " FROM stunt_revisions WHERE stunt_id = $1 ORDER BY revision_no DESC",
            stunt_id,
        )
        return [dict(r) for r in rows]


async def restore_revision(pool: asyncpg.Pool, actor_id: int, stunt_id: int, revision_id: int) -> dict:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_REVISIONS")
            # fetch พร้อม grid_data เดิม (STUNT_COLS ไม่มี grid_data — ต้องดึงแยกสำหรับ snapshot)
            stunt = await conn.fetchrow(
                "SELECT id, event_id, palette_a_id, palette_b_id, grid_width, grid_height, grid_data_a, grid_data_b"
                " FROM stunts WHERE id = $1 AND deleted_at IS NULL", stunt_id,
            )
            if not stunt:
                raise NotFoundError("ไม่พบ stunt")
            rev = await conn.fetchrow(
                "SELECT * FROM stunt_revisions WHERE id = $1 AND stunt_id = $2", revision_id, stunt_id,
            )
            if not rev:
                raise NotFoundError("ไม่พบ revision")
            from services.events_service import _bump_version
            await _bump_version(conn, stunt["event_id"])
            await conn.execute(
                "UPDATE stunts SET grid_width = $1, grid_height = $2, grid_data_a = $3, grid_data_b = $4,"
                " palette_a_id = $5, palette_b_id = $6, status = 'ready', updated_at = NOW(), updated_by = $7"
                " WHERE id = $8",
                rev["grid_width"], rev["grid_height"], rev["grid_data_a"], rev["grid_data_b"],
                rev["palette_a_id"], rev["palette_b_id"], actor_id, stunt_id,
            )
            await _snapshot_revision(conn, stunt_id, actor_id, f"restore revision {rev['revision_no']}", stunt)
            await AuditLogger("stunts").log(
                conn, "RESTORE_REVISION", str(actor_id), "web",
                user_id=actor_id, entity_type="stunt", entity_id=str(stunt_id),
                new_values={"revision_id": revision_id, "revision_no": rev["revision_no"]},
            )
            return _out(dict(await conn.fetchrow(f"SELECT {STUNT_COLS} FROM stunts WHERE id = $1", stunt_id)))


async def upload_reference(pool: asyncpg.Pool, actor_id: int, stunt_id: int, content: bytes, filename: str) -> dict:
    from core import media
    stunt = await get_stunt(pool, stunt_id)
    paths = await media.save_reference(stunt_id, content, filename)
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_STUNTS")
            from services.events_service import _bump_version
            await _bump_version(conn, stunt["event_id"])
            await conn.execute(
                "UPDATE stunts SET reference_image_path = $1, thumbnail_path = $2, updated_at = NOW(), updated_by = $3 WHERE id = $4",
                paths["reference_image_path"], paths["thumbnail_path"], actor_id, stunt_id,
            )
            await AuditLogger("stunts").log(
                conn, "UPLOAD_REFERENCE", str(actor_id), "web",
                user_id=actor_id, entity_type="stunt", entity_id=str(stunt_id),
            )
            return _out(dict(await conn.fetchrow(f"SELECT {STUNT_COLS} FROM stunts WHERE id = $1", stunt_id)))


async def stats(pool: asyncpg.Pool, stunt_id: int) -> dict:
    stunt = await get_stunt(pool, stunt_id)
    a = _json(stunt["grid_data_a"]) or []
    b = _json(stunt["grid_data_b"]) or []
    def counts(data):
        c = {}
        filled = 0
        for v in data:
            if v is not None:
                filled += 1
                c[str(v)] = c.get(str(v), 0) + 1
        return filled, c
    fa, ca = counts(a)
    fb, cb = counts(b)
    total = stunt["grid_width"] * stunt["grid_height"]
    return {
        "total_cells": total,
        "filled_a": fa, "filled_b": fb,
        "color_counts_a": ca, "color_counts_b": cb,
    }
