import asyncpg

from core.exceptions import NotFoundError, ValidationError
from core.logger import AuditLogger
from core.rbac import require_permission


async def _ensure_event(conn: asyncpg.Connection, event_id: int) -> None:
    if not await conn.fetchval("SELECT 1 FROM events WHERE id = $1 AND deleted_at IS NULL", event_id):
        raise NotFoundError("ไม่พบ event")


async def _queue_rows(conn: asyncpg.Connection, event_id: int):
    """คิวแสดง (เฉพาะ stunt ยังไม่ถูกลบ) เรียงตาม position."""
    return await conn.fetch(
        "SELECT q.position, q.stunt_id, s.code, s.title, s.side, s.status"
        " FROM live_queue q JOIN stunts s ON s.id = q.stunt_id"
        " WHERE q.event_id = $1 AND s.deleted_at IS NULL"
        " ORDER BY q.position",
        event_id,
    )


def _item(r) -> dict:
    return {
        "stunt_id": r["stunt_id"], "position": r["position"],
        "code": r["code"], "title": r["title"], "side": r["side"], "status": r["status"],
    }


async def _rewrite(conn: asyncpg.Connection, event_id: int, stunt_ids: list) -> None:
    """ลบคิวเดิมแล้วเขียนใหม่ด้วย position ต่อเนื่อง 0..n-1."""
    await conn.execute("DELETE FROM live_queue WHERE event_id = $1", event_id)
    for i, sid in enumerate(stunt_ids):
        await conn.execute(
            "INSERT INTO live_queue (event_id, position, stunt_id) VALUES ($1,$2,$3)",
            event_id, i, sid,
        )


async def get_queue(pool: asyncpg.Pool, actor_id: int, event_id: int) -> list:
    async with pool.acquire() as conn:
        await require_permission(conn, actor_id, "CONTROL_LIVE")
        await _ensure_event(conn, event_id)
        return [_item(r) for r in await _queue_rows(conn, event_id)]


async def set_queue(pool: asyncpg.Pool, actor_id: int, event_id: int, order: list) -> list:
    """แทนทั้งคิวด้วย `order` (เป็น subset ของฉากได้ — เลือกเฉพาะที่จะแสดงจริง)."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "CONTROL_LIVE")
            await _ensure_event(conn, event_id)
            valid = {
                r["id"] for r in await conn.fetch(
                    "SELECT id FROM stunts WHERE event_id = $1 AND deleted_at IS NULL", event_id,
                )
            }
            if len(set(order)) != len(order):
                raise ValidationError("order มี stunt ซ้ำ")
            if not set(order).issubset(valid):
                raise ValidationError("order มี stunt ที่ไม่อยู่ใน event นี้")
            await _rewrite(conn, event_id, order)
            await AuditLogger("live_queue").log(
                conn, "SET_QUEUE", str(actor_id), "web",
                user_id=actor_id, entity_type="event", entity_id=str(event_id),
                new_values={"order": order},
            )
            return [_item(r) for r in await _queue_rows(conn, event_id)]


async def insert_stunt(pool: asyncpg.Pool, actor_id: int, event_id: int, stunt_id: int, position: int) -> list:
    """แทรก stunt เข้าคิวที่ตำแหน่ง `position` (0-based) แล้ว renumber ตำแหน่งให้ต่อเนื่อง."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "CONTROL_LIVE")
            await _ensure_event(conn, event_id)
            ok = await conn.fetchval(
                "SELECT 1 FROM stunts WHERE id = $1 AND event_id = $2 AND deleted_at IS NULL", stunt_id, event_id,
            )
            if not ok:
                raise ValidationError("stunt ไม่อยู่ใน event นี้")
            rows = [r["stunt_id"] for r in await _queue_rows(conn, event_id)]
            if stunt_id in rows:
                raise ValidationError("stunt อยู่ในคิวแล้ว")
            position = max(0, min(int(position), len(rows)))
            rows.insert(position, stunt_id)
            await _rewrite(conn, event_id, rows)
            await AuditLogger("live_queue").log(
                conn, "INSERT_QUEUE", str(actor_id), "web",
                user_id=actor_id, entity_type="event", entity_id=str(event_id),
                new_values={"stunt_id": stunt_id, "position": position},
            )
            return [_item(r) for r in await _queue_rows(conn, event_id)]


async def remove_stunt(pool: asyncpg.Pool, actor_id: int, event_id: int, stunt_id: int) -> list:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "CONTROL_LIVE")
            await _ensure_event(conn, event_id)
            rows = [r["stunt_id"] for r in await _queue_rows(conn, event_id)]
            if stunt_id not in rows:
                raise NotFoundError("stunt ไม่อยู่ในคิว")
            rows.remove(stunt_id)
            await _rewrite(conn, event_id, rows)
            await AuditLogger("live_queue").log(
                conn, "REMOVE_QUEUE", str(actor_id), "web",
                user_id=actor_id, entity_type="event", entity_id=str(event_id),
                new_values={"stunt_id": stunt_id},
            )
            return [_item(r) for r in await _queue_rows(conn, event_id)]
