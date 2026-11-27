import json

import asyncpg

from core import cache
from core.config import settings
from core.exceptions import NotFoundError, ValidationError
from core.grid import StandGeometry, extract_plate, is_blocked, seat_labels


async def _get_public_event(conn: asyncpg.Connection, slug: str):
    row = await conn.fetchrow(
        "SELECT * FROM events WHERE slug = $1 AND deleted_at IS NULL", slug,
    )
    if not row:
        raise NotFoundError("ไม่พบ event")
    if not row["public_access_enabled"] or row["published_version"] <= 0:
        raise NotFoundError("event ยังไม่เผยแพร่")
    return row


def _jsonb(v):
    return json.loads(v) if isinstance(v, str) else (v or [])


async def meta(pool: asyncpg.Pool, slug: str):
    """คืน (body, etag, max_age) — router ประกอบ 304/headers เอง."""
    async with pool.acquire() as conn:
        ev = await _get_public_event(conn, slug)

        key = cache.cache_key(slug, ev["version"], "meta")
        body = await cache.get_json(key)
        if body is None:
            body = await _build_meta(conn, ev)
            await cache.set_json(key, body, settings.CACHE_META_TTL_SECONDS)

        return body, cache.etag_for(body), settings.CACHE_META_TTL_SECONDS


async def _build_meta(conn, ev) -> dict:
    stands = []
    for s in await conn.fetch(
        "SELECT * FROM stands WHERE event_id = $1 AND deleted_at IS NULL ORDER BY id", ev["id"],
    ):
        stands.append({
            "id": s["id"], "name": s["name"], "rows": s["rows"], "cols": s["cols"],
            "sub_rows": s["sub_rows"], "sub_cols": s["sub_cols"],
            "row_direction": s["row_direction"], "col_direction": s["col_direction"],
            "row_label_style": s["row_label_style"], "col_label_style": s["col_label_style"],
            "row_label_prefix": s["row_label_prefix"], "col_label_prefix": s["col_label_prefix"],
            "blocked_seats": _jsonb(s["blocked_seats"]),
        })

    palettes = []
    for p in await conn.fetch(
        "SELECT id, name FROM palettes WHERE event_id = $1 AND deleted_at IS NULL ORDER BY id", ev["id"],
    ):
        colors = [
            {"id": c["id"], "code": c["code"], "name_th": c["name_th"],
             "hex": c["hex"], "text_color": c["text_color"]}
            for c in await conn.fetch(
                "SELECT id, code, name_th, hex, text_color FROM palette_colors"
                " WHERE palette_id = $1 AND deleted_at IS NULL ORDER BY order_index, id", p["id"],
            )
        ]
        palettes.append({"id": p["id"], "name": p["name"], "colors": colors})

    stunts = [
        {"id": s["id"], "code": s["code"], "title": s["title"], "order_index": s["order_index"], "status": s["status"]}
        for s in await conn.fetch(
            "SELECT id, code, title, order_index, status FROM stunts"
            " WHERE event_id = $1 AND deleted_at IS NULL AND status = 'published' ORDER BY order_index, id",
            ev["id"],
        )
    ]
    live_ids = [s["id"] for s in stunts]
    idx = live_ids.index(ev["live_stunt_id"]) if ev["live_stunt_id"] in live_ids else None

    return {
        "slug": ev["slug"], "name": ev["name"], "published_version": ev["published_version"],
        "roster_lookup_enabled": ev["roster_lookup_enabled"],
        "event_date": ev["event_date"].isoformat() if ev["event_date"] else None,
        "stands": stands, "palettes": palettes, "stunts": stunts,
        "live": {
            "stunt_id": ev["live_stunt_id"], "stunt_index": idx, "total": len(stunts),
            "is_active": ev["live_is_active"], "published_version": ev["published_version"],
        },
    }


async def seat(pool: asyncpg.Pool, slug: str, row: int, col: int, stand_id=None):
    """row/col เป็น 1-based label (API public) — แปลงเป็น 0-based ก่อน. คืน (body, etag, max_age)."""
    async with pool.acquire() as conn:
        ev = await _get_public_event(conn, slug)
        stand = await _resolve_stand(conn, ev["id"], stand_id)
        g = StandGeometry(rows=stand["rows"], cols=stand["cols"], sub_rows=stand["sub_rows"],
                          sub_cols=stand["sub_cols"], row_direction=stand["row_direction"],
                          col_direction=stand["col_direction"])
        r0, c0 = row - 1, col - 1
        if not (0 <= r0 < g.rows and 0 <= c0 < g.cols):
            raise NotFoundError("พิกัดอยู่นอกแสตน")
        blocked = _jsonb(stand["blocked_seats"])
        if is_blocked(r0, c0, blocked):
            raise NotFoundError("ช่องนี้เป็นช่องปิด")

        key = cache.cache_key(slug, ev["version"], "seat", str(stand["id"]), str(r0), str(c0))
        body = await cache.get_json(key)
        if body is None:
            body = await _build_seat(conn, ev, stand, g, r0, c0)
            await cache.set_json(key, body, settings.CACHE_SEAT_TTL_SECONDS)

        return body, cache.etag_for(body), settings.CACHE_SEAT_TTL_SECONDS


async def seat_by_student_code(pool: asyncpg.Pool, slug: str, student_code: str):
    """ค้นที่นั่งจากเลขประจำตัว — ต้องเปิด `roster_lookup_enabled` ของ event."""
    code = (student_code or "").strip()
    if not code:
        raise ValidationError("กรุณากรอกเลขประจำตัว")
    async with pool.acquire() as conn:
        ev = await _get_public_event(conn, slug)
        if not ev["roster_lookup_enabled"]:
            raise NotFoundError("event นี้ปิดการค้นหาด้วยเลขประจำตัว")
        roster = await conn.fetchrow(
            "SELECT stand_id, row_index, col_index FROM seat_rosters"
            " WHERE event_id = $1 AND LOWER(student_code) = LOWER($2) AND deleted_at IS NULL"
            " ORDER BY id LIMIT 1",
            ev["id"], code,
        )
        if not roster:
            raise NotFoundError("ไม่พบเลขประจำตัวนี้ในงาน")

        stand = await conn.fetchrow(
            "SELECT * FROM stands WHERE id = $1 AND event_id = $2 AND deleted_at IS NULL",
            roster["stand_id"], ev["id"],
        )
        if not stand:
            raise NotFoundError("ไม่พบ stand ของที่นั่งนี้")
        g = StandGeometry(rows=stand["rows"], cols=stand["cols"], sub_rows=stand["sub_rows"],
                          sub_cols=stand["sub_cols"], row_direction=stand["row_direction"],
                          col_direction=stand["col_direction"])
        r0, c0 = roster["row_index"], roster["col_index"]
        if is_blocked(r0, c0, _jsonb(stand["blocked_seats"])):
            raise NotFoundError("ที่นั่งนี้เป็นช่องปิด")

        key = cache.cache_key(slug, ev["version"], "seat-code", str(stand["id"]), code.lower())
        body = await cache.get_json(key)
        if body is None:
            body = await _build_seat(conn, ev, stand, g, r0, c0)
            await cache.set_json(key, body, settings.CACHE_SEAT_TTL_SECONDS)
        return body, cache.etag_for(body), settings.CACHE_SEAT_TTL_SECONDS


async def _resolve_stand(conn, event_id, stand_id):
    if stand_id:
        s = await conn.fetchrow(
            "SELECT * FROM stands WHERE id = $1 AND event_id = $2 AND deleted_at IS NULL", stand_id, event_id,
        )
        if not s:
            raise NotFoundError("ไม่พบ stand")
        return s
    s = await conn.fetchrow(
        "SELECT * FROM stands WHERE event_id = $1 AND deleted_at IS NULL ORDER BY id LIMIT 1", event_id,
    )
    if not s:
        raise NotFoundError("event นี้ยังไม่มี stand")
    return s


async def _build_seat(conn, ev, stand, g, r0, c0) -> dict:
    rl, sl = seat_labels(r0, c0, g, stand["row_label_style"], stand["col_label_style"],
                         stand["row_label_prefix"], stand["col_label_prefix"])
    student = None
    # 🔒 แสดงข้อมูลนักเรียนเฉพาะเมื่อ event เปิด roster_lookup — endpoint seat เปิดให้ everyone
    #    ถ้าไม่ gate จะเท่ากับเปิดรายชื่อทั้งแสตนให้ใครก็ดึงได้ด้วยการยิง row/col ไล่ทีละช่อง
    if ev["roster_lookup_enabled"]:
        roster = await conn.fetchrow(
            "SELECT student_code, student_name FROM seat_rosters WHERE stand_id = $1 AND row_index = $2"
            " AND col_index = $3 AND deleted_at IS NULL", stand["id"], r0, c0,
        )
        if roster:
            student = {"student_code": roster["student_code"], "student_name": roster["student_name"]}

    stunts = []
    # ⚠️ ต้องกรอง stand_id ด้วย — งานที่มีหลายแสตน แต่ละแสตนมีฉากของตัวเอง
    #    ถ้าไม่กรอง ที่นั่งจะเห็นฉากของแสตนอื่นด้วย (และเพลทอาจถูก extract ผิดกริด)
    for s in await conn.fetch(
        "SELECT id, code, title, notes, grid_width, grid_height, grid_data_a, grid_data_b FROM stunts"
        " WHERE event_id = $1 AND stand_id = $2 AND deleted_at IS NULL AND status = 'published'"
        " ORDER BY order_index, id",
        ev["id"], stand["id"],
    ):
        a = _jsonb(s["grid_data_a"])
        b = _jsonb(s["grid_data_b"])
        plate_a = extract_plate(a, g, r0, c0) if len(a) == s["grid_width"] * s["grid_height"] else None
        plate_b = extract_plate(b, g, r0, c0) if len(b) == s["grid_width"] * s["grid_height"] else None
        stunts.append({
            "id": s["id"], "code": s["code"], "title": s["title"], "notes": s["notes"],
            "side_a": plate_a, "side_b": plate_b,
        })

    return {
        "slug": ev["slug"], "stand_id": stand["id"], "row_index": r0, "col_index": c0,
        "row_label": rl, "seat_label": sl, "student": student, "stunts": stunts,
    }


async def version(pool: asyncpg.Pool, slug: str):
    async with pool.acquire() as conn:
        ev = await _get_public_event(conn, slug)
        body = {"published_version": ev["published_version"], "updated_at": ev["updated_at"].isoformat()}
        return body, cache.etag_for(body), 30


def respond_cached(body, etag, max_age, if_none_match):
    """ประกอบ HTTP response พร้อม ETag/304 — ใช้ร่วมทุก public endpoint."""
    from fastapi import Response
    headers = {
        "ETag": etag,
        "Cache-Control": f"public, max-age={max_age}, stale-while-revalidate=60",
    }
    if if_none_match == etag:
        return Response(status_code=304, headers=headers)
    import json as _json
    return Response(
        content=_json.dumps(body, ensure_ascii=False, default=str),
        media_type="application/json",
        headers=headers,
    )
