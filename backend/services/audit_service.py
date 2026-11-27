import base64
import json

import asyncpg

from core.exceptions import ForbiddenError, ValidationError
from core.rbac import require_permission

DEFAULT_LIMIT = 30
MAX_LIMIT = 100


def _encode_cursor(created_at, row_id) -> str:
    raw = f"{created_at.isoformat()}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str):
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        ts_part, id_part = raw.split("|", 1)
        from datetime import datetime
        return datetime.fromisoformat(ts_part), int(id_part)
    except (ValueError, UnicodeDecodeError) as e:
        raise ValidationError("cursor ไม่ถูกต้อง") from e


async def list_audit_logs(pool: asyncpg.Pool, user_id: int, *, action=None, entity_type=None,
                          entity_id=None, status=None, service_name=None, q=None,
                          limit=DEFAULT_LIMIT, cursor=None) -> dict:
    safe_limit = min(max(int(limit), 1), MAX_LIMIT)
    cur_ts = cur_id = None
    if cursor:
        cur_ts, cur_id = _decode_cursor(cursor)

    async with pool.acquire() as conn:
        await require_permission(conn, user_id, "VIEW_AUDIT_LOG")
        where = ["1=1"]
        params = []
        for col, val in (("service_name", service_name), ("action", action),
                         ("entity_type", entity_type), ("entity_id", entity_id),
                         ("status", status)):
            if val:
                params.append(val)
                where.append(f"{col} = ${len(params)}")
        if q and q.strip():
            params.append(f"%{q.strip()}%")
            n = len(params)
            where.append(f"(actor_identifier ILIKE ${n} OR endpoint_or_command ILIKE ${n}"
                         f" OR entity_id ILIKE ${n} OR error_detail ILIKE ${n})")
        if cur_ts is not None and cur_id is not None:
            params.append(cur_ts)
            t = len(params)
            params.append(cur_id)
            i = len(params)
            where.append(f"(created_at, id) < (${t}::timestamptz, ${i})")

        params.append(safe_limit + 1)
        limit_idx = len(params)
        rows = await conn.fetch(
            f"""
            SELECT id, trace_id, user_id, actor_identifier, client_source, service_name, action,
                   entity_type, entity_id, status, error_detail, old_values, new_values,
                   endpoint_or_command, ip_address, user_agent, execution_time_ms, created_at
            FROM audit_logs
            WHERE {" AND ".join(where)}
            ORDER BY created_at DESC, id DESC
            LIMIT ${limit_idx}
            """,
            *params,
        )
    has_more = len(rows) > safe_limit
    items = rows[:safe_limit]
    next_cursor = None
    if has_more:
        last = items[-1]
        next_cursor = _encode_cursor(last["created_at"], last["id"])

    return {
        "items": [_to_dict(r) for r in items],
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


def _to_dict(r) -> dict:
    out = dict(r)
    for k in ("old_values", "new_values"):
        v = out.get(k)
        out[k] = json.loads(v) if isinstance(v, str) else v
    return out


async def get_options(pool: asyncpg.Pool, user_id: int) -> dict:
    async with pool.acquire() as conn:
        await require_permission(conn, user_id, "VIEW_AUDIT_LOG")
        async def distinct(col):
            rows = await conn.fetch(
                f"SELECT DISTINCT {col} AS v FROM audit_logs WHERE {col} <> '-'"
                f" AND created_at > NOW() - INTERVAL '90 days' ORDER BY v LIMIT 200"
            )
            return [r["v"] for r in rows]
        return {
            "actions": await distinct("action"),
            "statuses": await distinct("status"),
            "entity_types": await distinct("entity_type"),
            "service_names": await distinct("service_name"),
        }
