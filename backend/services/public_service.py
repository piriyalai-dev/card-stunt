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


async def _live_block(conn, ev) -> dict:
    # live state จากคิวแสดง (live_queue) — meta ต้องไม่พกเนื้อหาฉาก (ล็อกดาวน์)
    ids = [
        r["id"] for r in await conn.fetch(
            "SELECT s.id FROM live_queue q JOIN stunts s ON s.id = q.stunt_id"
            " WHERE q.event_id = $1 AND s.deleted_at IS NULL AND s.status = 'published'"
            " ORDER BY q.position", ev["id"],
        )
    ]
    idx = ids.index(ev["live_stunt_id"]) if ev["live_stunt_id"] in ids else None
    return {
        "stunt_id": ev["live_stunt_id"], "stunt_index": idx, "total": len(ids),
        "is_active": ev["live_is_active"], "published_version": ev["published_version"],
    }


async def _build_meta(conn, ev) -> dict:
    return {
        "slug": ev["slug"], "name": ev["name"], "published_version": ev["published_version"],
        "event_date": ev["event_date"].isoformat() if ev["event_date"] else None,
        "live": await _live_block(conn, ev),
    }


async def claim(pool: asyncpg.Pool, slug: str, access_code: str) -> dict:
    """ล็อกอินด้วยรหัสสุ่ม — คืน (seat + palettes + stunts) ของที่นั่งนั้น. ไม่แคช ETag (per-user)."""
    code = (access_code or "").strip().upper()
    if not code:
        raise ValidationError("กรุณากรอกรหัสล็อกอิน")
    async with pool.acquire() as conn:
        ev = await _get_public_event(conn, slug)
        roster = await conn.fetchrow(
            "SELECT stand_id, row_index, col_index, student_code, student_name FROM seat_rosters"
            " WHERE event_id = $1 AND access_code = $2 AND deleted_at IS NULL ORDER BY id LIMIT 1",
            ev["id"], code,
        )
        if not roster:
            raise NotFoundError("รหัสล็อกอินไม่ถูกต้อง")
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
        return await _build_seat(conn, ev, stand, g, r0, c0, roster)


async def _load_event_palettes(conn, event_id) -> list:
    """โหลด palette A/B ของ event พร้อมสี — ต้องแนบมากับ claim ไม่งั้น render plate ไม่ได้ออฟไลน์."""
    ev = await conn.fetchrow("SELECT palette_a_id, palette_b_id FROM events WHERE id = $1", event_id)
    ids = []
    for pid in (ev["palette_a_id"], ev["palette_b_id"]):
        if pid and pid not in ids:
            ids.append(pid)
    palettes = []
    for pid in ids:
        p = await conn.fetchrow("SELECT id, name FROM palettes WHERE id = $1 AND deleted_at IS NULL", pid)
        if not p:
            continue
        colors = [
            {"id": c["id"], "code": c["code"], "name_th": c["name_th"],
             "hex": c["hex"], "text_color": c["text_color"]}
            for c in await conn.fetch(
                "SELECT id, code, name_th, hex, text_color FROM palette_colors"
                " WHERE palette_id = $1 AND deleted_at IS NULL ORDER BY order_index, id", p["id"],
            )
        ]
        palettes.append({"id": p["id"], "name": p["name"], "colors": colors})
    return palettes


async def _build_seat(conn, ev, stand, g, r0, c0, roster) -> dict:
    rl, sl = seat_labels(r0, c0, g, stand["row_label_style"], stand["col_label_style"],
                         stand["row_label_prefix"], stand["col_label_prefix"])
    student = {"student_code": roster["student_code"], "student_name": roster["student_name"]}

    palettes = await _load_event_palettes(conn, ev["id"])

    stunts = []
    # ⚠️ ต้องกรอง stand_id — งานที่มีหลายแสตน แต่ละแสตนมีฉากของตัวเอง
    for s in await conn.fetch(
        "SELECT id, code, title, notes, side, grid_width, grid_height, grid_data FROM stunts"
        " WHERE event_id = $1 AND stand_id = $2 AND deleted_at IS NULL AND status = 'published'"
        " ORDER BY order_index, id",
        ev["id"], stand["id"],
    ):
        grid = _jsonb(s["grid_data"])
        plate = extract_plate(grid, g, r0, c0) if len(grid) == s["grid_width"] * s["grid_height"] else None
        stunts.append({
            "id": s["id"], "code": s["code"], "title": s["title"], "notes": s["notes"],
            "side": s["side"], "plate": plate,
        })

    return {
        "slug": ev["slug"], "stand_id": stand["id"], "row_index": r0, "col_index": c0,
        "row_label": rl, "seat_label": sl, "student": student,
        "palettes": palettes, "stunts": stunts,
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
