import csv
import io
import json
import secrets

import asyncpg

from core.config import settings
from core.exceptions import ConflictError, NotFoundError, PayloadTooLargeError, ValidationError
from core.grid import StandGeometry, is_blocked, seat_labels
from core.logger import AuditLogger
from core.ratelimit import check_rate_limit
from core.rbac import require_permission

ROSTER_COLS = "id, event_id, stand_id, row_index, col_index, row_label, seat_label, student_code, access_code, student_name, note, created_at, updated_at"

# charset ไม่กำกวม (ตัด 0/O/1/I) — รหัสล็อกอินที่พิมพ์แจกนักเรียน
_ACCESS_CODE_CHARSET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _random_access_code() -> str:
    return "".join(secrets.choice(_ACCESS_CODE_CHARSET) for _ in range(8))


async def _mint_access_code(conn: asyncpg.Connection, event_id: int) -> str:
    """สร้างรหัสล็อกอินสุ่ม unique ต่อ event (unique index เป็น safety net กัน race)."""
    for _ in range(10):
        code = _random_access_code()
        exists = await conn.fetchval(
            "SELECT 1 FROM seat_rosters WHERE event_id = $1 AND access_code = $2 AND deleted_at IS NULL",
            event_id, code,
        )
        if not exists:
            return code
    raise ConflictError("สร้างรหัสล็อกอินไม่สำเร็จ (ชนกัน) — ลองใหม่")


async def get_roster(pool: asyncpg.Pool, roster_id: int) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT {ROSTER_COLS} FROM seat_rosters WHERE id = $1 AND deleted_at IS NULL", roster_id,
        )
        if not row:
            raise NotFoundError("ไม่พบ roster")
        return dict(row)


async def list_rosters(pool: asyncpg.Pool, event_id: int, stand_id=None) -> list:
    async with pool.acquire() as conn:
        if stand_id:
            rows = await conn.fetch(
                f"SELECT {ROSTER_COLS} FROM seat_rosters WHERE event_id = $1 AND stand_id = $2 AND deleted_at IS NULL"
                " ORDER BY row_index, col_index", event_id, stand_id,
            )
        else:
            rows = await conn.fetch(
                f"SELECT {ROSTER_COLS} FROM seat_rosters WHERE event_id = $1 AND deleted_at IS NULL"
                " ORDER BY stand_id, row_index, col_index", event_id,
            )
    return [dict(r) for r in rows]


async def create_roster(pool: asyncpg.Pool, actor_id: int, event_id: int, data: dict) -> dict:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_ROSTERS")
            row = await _validate_seat(conn, event_id, data["stand_id"], data["row_index"], data["col_index"])
            g = _geom(row)
            rl, sl = seat_labels(data["row_index"], data["col_index"], g,
                                 row["row_label_style"], row["col_label_style"],
                                 row["row_label_prefix"], row["col_label_prefix"])
            access_code = await _mint_access_code(conn, event_id)
            try:
                rid = await conn.fetchval(
                    "INSERT INTO seat_rosters (event_id, stand_id, row_index, col_index, row_label, seat_label,"
                    " student_code, access_code, student_name, note) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING id",
                    event_id, data["stand_id"], data["row_index"], data["col_index"], rl, sl,
                    data.get("student_code"), access_code, data["student_name"], data.get("note"),
                )
            except asyncpg.UniqueViolationError:
                raise ConflictError("ที่นั่งนี้มีนักเรียนอยู่แล้ว (หรือ student_code ซ้ำ)")
            await AuditLogger("rosters").log(
                conn, "CREATE_ROSTER", str(actor_id), "web",
                user_id=actor_id, entity_type="roster", entity_id=str(rid),
                new_values={"stand_id": data["stand_id"], "row": data["row_index"], "col": data["col_index"]},
            )
            out = await conn.fetchrow(f"SELECT {ROSTER_COLS} FROM seat_rosters WHERE id = $1", rid)
    return dict(out)


async def update_roster(pool: asyncpg.Pool, actor_id: int, roster_id: int, data: dict) -> dict:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_ROSTERS")
            row = await conn.fetchrow(
                f"SELECT {ROSTER_COLS} FROM seat_rosters WHERE id = $1 AND deleted_at IS NULL", roster_id,
            )
            if not row:
                raise NotFoundError("ไม่พบ roster")
            sets, params = [], []
            for col in ("student_code", "student_name", "note"):
                if data.get(col) is not None:
                    params.append(data[col])
                    sets.append(f"{col} = ${len(params)}")
            if sets:
                sets.append("updated_at = NOW()")
                params.append(roster_id)
                try:
                    await conn.execute(f"UPDATE seat_rosters SET {', '.join(sets)} WHERE id = ${len(params)}", *params)
                except asyncpg.UniqueViolationError:
                    raise ConflictError("student_code ซ้ำใน event นี้")
            await AuditLogger("rosters").log(
                conn, "UPDATE_ROSTER", str(actor_id), "web",
                user_id=actor_id, entity_type="roster", entity_id=str(roster_id), new_values=data,
            )
            out = await conn.fetchrow(f"SELECT {ROSTER_COLS} FROM seat_rosters WHERE id = $1", roster_id)
    return dict(out)


async def delete_roster(pool: asyncpg.Pool, actor_id: int, roster_id: int) -> None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_ROSTERS")
            row = await conn.fetchrow(
                "SELECT id FROM seat_rosters WHERE id = $1 AND deleted_at IS NULL", roster_id,
            )
            if not row:
                raise NotFoundError("ไม่พบ roster")
            await conn.execute("UPDATE seat_rosters SET deleted_at = NOW() WHERE id = $1", roster_id)
            await AuditLogger("rosters").log(
                conn, "DELETE_ROSTER", str(actor_id), "web",
                user_id=actor_id, entity_type="roster", entity_id=str(roster_id),
            )


async def import_roster(pool: asyncpg.Pool, actor_id: int, event_id: int, stand_id: int, content: bytes, filename: str) -> dict:
    """import CSV/XLSX — คอลัมน์ row/col (0-based หรือ 1-based ตาม label), student_code, student_name, note."""
    await check_rate_limit(
        [f"pixelstand:ratelimit:import:user:{actor_id}"],
        settings.BULK_OP_RATE_LIMIT_MAX, settings.BULK_OP_RATE_LIMIT_WINDOW_SECONDS,
    )
    if len(content) > settings.ROSTER_FILE_SIZE_LIMIT_MB * 1024 * 1024:
        raise PayloadTooLargeError(f"ไฟล์เกิน {settings.ROSTER_FILE_SIZE_LIMIT_MB} MB")

    rows = _parse_file(content, filename)
    if len(rows) > settings.ROSTER_MAX_ROWS:
        raise ValidationError(f"เกิน {settings.ROSTER_MAX_ROWS} แถว")

    inserted = 0
    errors = []
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_ROSTERS")
            stand = await conn.fetchrow(
                "SELECT * FROM stands WHERE id = $1 AND event_id = $2 AND deleted_at IS NULL", stand_id, event_id,
            )
            if not stand:
                raise NotFoundError("ไม่พบ stand")
            g = _geom(stand)
            blocked = json.loads(stand["blocked_seats"]) if isinstance(stand["blocked_seats"], str) else stand["blocked_seats"]

            for i, r in enumerate(rows):
                try:
                    row_index, col_index = _parse_seat(r, g)
                    if is_blocked(row_index, col_index, blocked):
                        raise ValidationError(f"ช่อง ({row_index},{col_index}) เป็นช่องปิด")
                    rl, sl = seat_labels(row_index, col_index, g, stand["row_label_style"], stand["col_label_style"],
                                         stand["row_label_prefix"], stand["col_label_prefix"])
                    student_code = (_cell_text(r.get("student_code")) or _cell_text(r.get("code"))) or None
                    student_name = (_cell_text(r.get("student_name")) or _cell_text(r.get("name")))
                    if not student_name:
                        raise ValidationError("student_name ห้ามว่าง")
                    access_code = await _mint_access_code(conn, event_id)
                    try:
                        await conn.execute(
                            "INSERT INTO seat_rosters (event_id, stand_id, row_index, col_index, row_label,"
                            " seat_label, student_code, access_code, student_name, note)"
                            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)",
                            event_id, stand_id, row_index, col_index, rl, sl, student_code,
                            access_code, student_name, r.get("note"),
                        )
                        inserted += 1
                    except asyncpg.UniqueViolationError:
                        errors.append(f"แถว {i + 1}: ที่นั่งซ้ำหรือ student_code ซ้ำ")
                except ValidationError as e:
                    errors.append(f"แถว {i + 1}: {e}")

            await AuditLogger("rosters").log(
                conn, "IMPORT_ROSTER", str(actor_id), "web",
                user_id=actor_id, entity_type="event", entity_id=str(event_id),
                new_values={"stand_id": stand_id, "inserted": inserted, "errors": len(errors)},
            )
    return {"inserted": inserted, "errors": errors, "total": len(rows)}


def _parse_file(content: bytes, filename: str) -> list:
    lower = filename.lower()
    if lower.endswith(".xlsx"):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
        ws = wb.active
        it = ws.iter_rows(values_only=True)
        header = [str(c).strip() if c is not None else "" for c in next(it)]
        out = []
        for row in it:
            out.append(dict(zip(header, row)))
        return out
    if lower.endswith(".xls"):
        # openpyxl อ่าน legacy BIFF/OLE .xls ไม่ได้ → กัน 500 ดิบ (บทเรียน prsc_portal skills.md)
        raise ValidationError("ไฟล์ .xls (BIFF/OLE) ไม่รองรับ — เซฟเป็น .xlsx หรือ CSV แล้วลองใหม่")
    # CSV
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(r) for r in reader]


def _cell_text(v) -> str:
    """แปลงค่าเซลล์ (int/float/str/None) → str · ตัด `.0` ของ float ที่ลงตัว (40000.0 → "40000")."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _parse_seat(r: dict, g: StandGeometry):
    """รับ row/col แบบ 1-based (label) หรือ 0-based (row_index) — ตามชื่อคอลัมน์."""
    def to_int(v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return int(v)
        s = str(v).strip()
        return int(s) if s else None

    # ยอมรับชื่อคอลัมน์ได้หลายแบบ (ไทย/อังกฤษ)
    row_v = r.get("row_index", r.get("row", r.get("แถว")))
    col_v = r.get("col_index", r.get("col", r.get("col_seat", r.get("ที่นั่ง"))))
    row = to_int(row_v)
    col = to_int(col_v)
    if row is None or col is None:
        raise ValidationError("ไม่มีคอลัมน์ row/col")

    # label (1-based) ถ้าใช้ชื่อ row/col ตรง ๆ → แปลงเป็น 0-based
    if "row_index" in r or "col_index" in r:
        return row, col  # 0-based อยู่แล้ว
    # ค่าแบบ 1-based label → ลบ 1
    row = row - 1
    col = col - 1
    if not (0 <= row < g.rows and 0 <= col < g.cols):
        raise ValidationError(f"พิกัด ({row},{col}) อยู่นอกแสตน")
    return row, col


def _geom(row) -> StandGeometry:
    return StandGeometry(rows=row["rows"], cols=row["cols"], sub_rows=row["sub_rows"],
                         sub_cols=row["sub_cols"], row_direction=row["row_direction"],
                         col_direction=row["col_direction"])


async def _validate_seat(conn, event_id, stand_id, row_index, col_index):
    row = await conn.fetchrow(
        "SELECT * FROM stands WHERE id = $1 AND event_id = $2 AND deleted_at IS NULL", stand_id, event_id,
    )
    if not row:
        raise NotFoundError("ไม่พบ stand")
    g = _geom(row)
    if not (0 <= row_index < g.rows and 0 <= col_index < g.cols):
        raise ValidationError("พิกัดอยู่นอกแสตน")
    blocked = json.loads(row["blocked_seats"]) if isinstance(row["blocked_seats"], str) else row["blocked_seats"]
    if is_blocked(row_index, col_index, blocked):
        raise ValidationError("ช่องนี้เป็นช่องปิด (blocked)")
    return row
