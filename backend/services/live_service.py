import asyncpg

from core.exceptions import NotFoundError, ValidationError
from core.logger import AuditLogger
from core.rbac import require_permission


async def get_live_state(pool: asyncpg.Pool, event_id: int) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, slug, live_stunt_id, live_is_active, live_updated_at, published_version FROM events"
            " WHERE id = $1 AND deleted_at IS NULL", event_id,
        )
        if not row:
            raise NotFoundError("ไม่พบ event")
        return await _state(conn, row)


async def _state(conn, event_row) -> dict:
    stunts = await conn.fetch(
        "SELECT id, order_index FROM stunts WHERE event_id = $1 AND deleted_at IS NULL AND status = 'published'"
        " ORDER BY order_index, id",
        event_row["id"],
    )
    ids = [s["id"] for s in stunts]
    idx = ids.index(event_row["live_stunt_id"]) if event_row["live_stunt_id"] in ids else None
    return {
        "event_id": event_row["id"],
        "slug": event_row["slug"],
        "current_stunt_id": event_row["live_stunt_id"],
        "current_index": idx,
        "total": len(ids),
        "published_version": event_row["published_version"],
        "is_active": event_row["live_is_active"],
        "stunt_ids": ids,
    }


async def advance(pool: asyncpg.Pool, actor_id: int, event_id: int, action: str, stunt_id=None) -> dict:
    """next/prev/goto — เฉพาะ stunt ที่ published เท่านั้น · update live + trigger notify."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "CONTROL_LIVE")
            row = await conn.fetchrow(
                "SELECT id FROM events WHERE id = $1 AND deleted_at IS NULL", event_id,
            )
            if not row:
                raise NotFoundError("ไม่พบ event")
            ids = [
                s["id"] for s in await conn.fetch(
                    "SELECT id FROM stunts WHERE event_id = $1 AND deleted_at IS NULL AND status = 'published'"
                    " ORDER BY order_index, id", event_id,
                )
            ]
            if not ids:
                raise ValidationError("ยังไม่มี stunt ที่ published")

            current = await conn.fetchval("SELECT live_stunt_id FROM events WHERE id = $1", event_id)
            if action == "goto":
                if stunt_id not in ids:
                    raise ValidationError("stunt ไม่ได้อยู่ในคิว published")
                nxt = stunt_id
            elif action == "next":
                idx = ids.index(current) if current in ids else -1
                nxt = ids[(idx + 1) % len(ids)]
            elif action == "prev":
                idx = ids.index(current) if current in ids else 0
                nxt = ids[(idx - 1) % len(ids)]
            else:
                raise ValidationError("action ต้องเป็น next/prev/goto")

            await conn.execute(
                "UPDATE events SET live_stunt_id = $1, live_is_active = TRUE, live_updated_at = NOW(),"
                " live_updated_by = $2, updated_at = NOW() WHERE id = $3",
                nxt, actor_id, event_id,
            )
            await AuditLogger("live").log(
                conn, "ADVANCE_LIVE", str(actor_id), "web",
                user_id=actor_id, entity_type="event", entity_id=str(event_id),
                new_values={"action": action, "to_stunt": nxt},
            )
            fresh = await conn.fetchrow(
                "SELECT id, slug, live_stunt_id, live_is_active, live_updated_at, published_version FROM events"
                " WHERE id = $1", event_id,
            )
            return await _state(conn, fresh)
