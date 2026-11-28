"""📦 Export jobs — สร้าง/ติดตาม/ดาวน์โหลด PDF · CSV · ZIP

- `create_export` เขียนแถว `export_jobs` แล้ว **enqueue ผ่าน ARQ** (best-effort)
- `run_export` คือตัวงานที่ worker เรียก — โหลดข้อมูล → builder → เขียนไฟล์ → อัปเดตสถานะ
- ไฟล์เก็บใต้ `EXPORT_STORAGE_DIR` แบบ relative path (`exports/<job_id>/export.<ext>`)
"""
import logging
import os
import shutil
import time
import uuid

import asyncpg

from core import exports_io
from core.config import settings
from core.exceptions import ConflictError, NotFoundError, ValidationError
from core.logger import AuditLogger
from core.ratelimit import check_rate_limit
from core.rbac import require_permission
from services import export_builders

logger = logging.getLogger("EXPORTS")

EXPORT_COLS = (
    "id, event_id, stand_id, format, scope, status, file_path, error,"
    " requested_by, created_at, completed_at"
)

_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "csv": "text/csv; charset=utf-8",
    "zip": "application/zip",
}
_EXTENSIONS = {"pdf": "pdf", "csv": "csv", "zip": "zip"}


# ── create / list / retry ───────────────────────────────────────────

async def create_export(pool: asyncpg.Pool, actor_id: int, event_id: int, data: dict) -> dict:
    await check_rate_limit(
        [f"pixelstand:ratelimit:export:user:{actor_id}"],
        settings.BULK_OP_RATE_LIMIT_MAX, settings.BULK_OP_RATE_LIMIT_WINDOW_SECONDS,
    )
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "EXPORT")
            ok = await conn.fetchval("SELECT 1 FROM events WHERE id = $1 AND deleted_at IS NULL", event_id)
            if not ok:
                raise NotFoundError("ไม่พบ event")
            if data.get("stand_id"):
                sok = await conn.fetchval(
                    "SELECT 1 FROM stands WHERE id = $1 AND event_id = $2 AND deleted_at IS NULL",
                    data["stand_id"], event_id,
                )
                if not sok:
                    raise ValidationError("stand ไม่อยู่ใน event นี้")
            jid = await conn.fetchval(
                "INSERT INTO export_jobs (event_id, stand_id, format, scope, requested_by)"
                " VALUES ($1,$2,$3,$4,$5) RETURNING id",
                event_id, data.get("stand_id"), data["format"], data.get("scope", "event"), actor_id,
            )
            await AuditLogger("exports").log(
                conn, "CREATE_EXPORT", str(actor_id), "web",
                user_id=actor_id, entity_type="export_job", entity_id=str(jid),
                new_values={"format": data["format"], "scope": data.get("scope", "event")},
            )
            row = dict(await conn.fetchrow(f"SELECT {EXPORT_COLS} FROM export_jobs WHERE id = $1", jid))

    # enqueue หลัง commit — ถ้า Redis ล่ม job ยังอยู่ใน DB เป็น queued (retry ได้)
    await enqueue_export(jid)
    return row


async def list_exports(pool: asyncpg.Pool, actor_id: int, event_id: int, limit: int = 100) -> list:
    async with pool.acquire() as conn:
        await require_permission(conn, actor_id, "EXPORT")
        rows = await conn.fetch(
            f"SELECT {EXPORT_COLS} FROM export_jobs"
            " WHERE event_id = $1 AND deleted_at IS NULL ORDER BY id DESC LIMIT $2",
            event_id, max(1, min(500, limit)),
        )
    return [dict(r) for r in rows]


async def get_export(pool: asyncpg.Pool, job_id: int, actor_id: int | None = None):
    async with pool.acquire() as conn:
        if actor_id is not None:
            await require_permission(conn, actor_id, "EXPORT")
        row = await conn.fetchrow(
            f"SELECT {EXPORT_COLS} FROM export_jobs WHERE id = $1 AND deleted_at IS NULL", job_id,
        )
        if not row:
            raise NotFoundError("ไม่พบ export job")
        return dict(row)


async def retry_export(pool: asyncpg.Pool, actor_id: int, job_id: int) -> dict:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "EXPORT")
            row = await conn.fetchrow(
                "SELECT id, status FROM export_jobs WHERE id = $1 AND deleted_at IS NULL", job_id,
            )
            if not row:
                raise NotFoundError("ไม่พบ export job")
            if row["status"] == "running":
                raise ConflictError("งานนี้กำลังสร้างไฟล์อยู่ — รอให้เสร็จก่อน")
            await conn.execute(
                "UPDATE export_jobs SET status = 'queued', error = NULL, file_path = NULL,"
                " completed_at = NULL WHERE id = $1", job_id,
            )
            await AuditLogger("exports").log(
                conn, "RETRY_EXPORT", str(actor_id), "web",
                user_id=actor_id, entity_type="export_job", entity_id=str(job_id),
            )
            out = dict(await conn.fetchrow(f"SELECT {EXPORT_COLS} FROM export_jobs WHERE id = $1", job_id))
    await enqueue_export(job_id)
    return out


async def download_export(pool: asyncpg.Pool, actor_id: int, job_id: int) -> tuple[str, str, str]:
    """คืน (absolute_path, filename, media_type) — ให้ router ตอบ FileResponse."""
    async with pool.acquire() as conn:
        await require_permission(conn, actor_id, "EXPORT")
        row = await conn.fetchrow(
            "SELECT j.status, j.file_path, j.format, j.id, e.slug"
            " FROM export_jobs j JOIN events e ON e.id = j.event_id"
            " WHERE j.id = $1 AND j.deleted_at IS NULL", job_id,
        )
        if not row:
            raise NotFoundError("ไม่พบ export job")
    if row["status"] != "done" or not row["file_path"]:
        raise ConflictError("export ยังไม่เสร็จ — ลองใหม่เมื่อสถานะเป็น done")

    path = exports_io.resolve(row["file_path"])
    ext = _EXTENSIONS.get(row["format"], "bin")
    filename = f"{row['slug']}-{row['format']}-{job_id}.{ext}"
    return path, filename, _MEDIA_TYPES.get(row["format"], "application/octet-stream")


# ── queue ───────────────────────────────────────────────────────────

async def enqueue_export(job_id: int) -> bool:
    """push งานเข้า ARQ — คืน False ถ้า Redis ยังไม่พร้อม (job ค้าง queued)."""
    if not settings.REDIS_URL:
        logger.info("REDIS_URL ว่าง — export job %s ค้าง queued", job_id)
        return False
    try:
        from arq.connections import RedisSettings, create_pool

        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        try:
            await redis.enqueue_job(
                "generate_export", job_id,
                # job id ไม่ซ้ำ ⇒ กด retry ซ้ำได้ (ARQ ไม่ปฏิเสธเพราะคีย์เดิม)
                _job_id=f"export:{job_id}:{uuid.uuid4().hex}",
            )
        finally:
            await redis.aclose()
        return True
    except Exception as exc:  # noqa: BLE001 — queue ล่มต้องไม่ทำให้ API 500
        logger.warning("enqueue export %s ไม่สำเร็จ: %s", job_id, exc)
        return False


# ── worker entrypoint ───────────────────────────────────────────────

async def run_export(pool: asyncpg.Pool, job_id: int) -> None:
    """เรียกโดย ARQ worker (หรือเทสต์ตรง ๆ) — จบเสมอด้วย status done/failed."""
    job = await get_export(pool, job_id)
    if job["status"] == "done" and job["file_path"] and _file_exists(job["file_path"]):
        return

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE export_jobs SET status = 'running', error = NULL WHERE id = $1", job_id,
        )

    try:
        data = await _load_data(pool, job)
        content, ext = _render(job, data)
        rel_path = f"exports/{job_id}/export.{ext}"
        exports_io.write(rel_path, content)

        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE export_jobs SET status = 'done', file_path = $1, error = NULL,"
                    " completed_at = NOW() WHERE id = $2",
                    rel_path, job_id,
                )
                await AuditLogger("exports").log(
                    conn, "EXPORT_DONE", str(job.get("requested_by") or "-"), "worker",
                    user_id=job.get("requested_by"), entity_type="export_job", entity_id=str(job_id),
                    new_values={"format": job["format"], "file_path": rel_path},
                    endpoint_or_command="arq:generate_export",
                )
    except Exception as exc:  # noqa: BLE001 — ต้องบันทึกเหตุผลลง DB ให้ UI เห็น
        logger.exception("export job %s ล้มเหลว", job_id)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE export_jobs SET status = 'failed', error = $1, completed_at = NOW()"
                " WHERE id = $2", str(exc)[:1000], job_id,
            )
            await AuditLogger("exports").log(
                conn, "EXPORT_FAILED", str(job.get("requested_by") or "-"), "worker",
                user_id=job.get("requested_by"), entity_type="export_job", entity_id=str(job_id),
                status="error", error_detail=str(exc)[:500],
                endpoint_or_command="arq:generate_export",
            )


def _file_exists(rel_path: str) -> bool:
    try:
        exports_io.resolve(rel_path)
        return True
    except Exception:  # noqa: BLE001
        return False


# ── retention (worker cron) ─────────────────────────────────────────

async def purge_expired_exports(pool: asyncpg.Pool) -> int:
    """ลบโฟลเดอร์ export ที่เก่ากว่า `EXPORT_MAX_AGE_DAYS` แล้วเคลียร์ `file_path` ใน DB.

    ⚠️ ลบ **โฟลเดอร์ต่อ job** (`exports/<id>/`) ไม่ใช่ไล่ไฟล์ทีละไฟล์ — job หนึ่งมีไฟล์เดียว
    ในดีไซน์นี้ แต่การลบทั้งโฟลเดอร์กันไฟล์ `.tmp` ค้างจากการเขียนที่ล้มกลางทาง
    """
    days = settings.EXPORT_MAX_AGE_DAYS
    if days <= 0:
        return 0

    root = os.path.abspath(os.path.join(settings.EXPORT_STORAGE_DIR, "exports"))
    if not os.path.isdir(root):
        return 0

    cutoff = time.time() - days * 86400
    removed: list[int] = []
    for name in os.listdir(root):
        path = os.path.join(root, name)
        if not (os.path.isdir(path) and name.isdigit()):
            continue
        try:
            if os.path.getmtime(path) >= cutoff:
                continue
            shutil.rmtree(path, ignore_errors=True)
            removed.append(int(name))
        except OSError:
            continue

    if removed:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE export_jobs SET file_path = NULL,"
                " error = 'ไฟล์ถูกลบตาม retention (EXPORT_MAX_AGE_DAYS)'"
                " WHERE id = ANY($1::int[]) AND status = 'done'",
                removed,
            )
        logger.info("purge export: ลบ %s งานเก่า", len(removed))
    return len(removed)


def _render(job: dict, data: dict) -> tuple[bytes, str]:
    event = data["event"]
    stands = data["stands"]
    palettes = data["palettes"]
    stunts = data["stunts"]
    rosters = data["rosters"]

    records = export_builders.seat_records(event, stands, palettes, stunts, rosters)

    if job["format"] == "pdf":
        if len(records) > settings.EXPORT_MAX_SEATS_PDF:
            raise ValidationError(
                f"ที่นั่ง {len(records)} เกินเพดาน PDF {settings.EXPORT_MAX_SEATS_PDF}"
                " — เลือก export เฉพาะ stand"
            )
        return export_builders.build_pdf(event, records, palettes), "pdf"
    if job["format"] == "csv":
        return export_builders.build_csv(records, palettes), "csv"
    if job["format"] == "zip":
        return export_builders.build_zip(event, stands, palettes, stunts, records), "zip"
    raise ValidationError(f"ไม่รู้จัก format: {job['format']}")


async def _load_data(pool: asyncpg.Pool, job: dict) -> dict:
    async with pool.acquire() as conn:
        event = await conn.fetchrow(
            "SELECT id, slug, name, event_date FROM events WHERE id = $1 AND deleted_at IS NULL",
            job["event_id"],
        )
        if not event:
            raise NotFoundError("ไม่พบ event")
        event = dict(event)
        event["event_date"] = event["event_date"].isoformat() if event["event_date"] else None

        if job.get("stand_id"):
            stand_rows = await conn.fetch(
                "SELECT * FROM stands WHERE id = $1 AND event_id = $2 AND deleted_at IS NULL",
                job["stand_id"], event["id"],
            )
        else:
            stand_rows = await conn.fetch(
                "SELECT * FROM stands WHERE event_id = $1 AND deleted_at IS NULL ORDER BY id",
                event["id"],
            )
        stands = [dict(r) for r in stand_rows]

        if job.get("stand_id"):
            stunt_rows = await conn.fetch(
                "SELECT * FROM stunts WHERE event_id = $1 AND stand_id = $2"
                " AND deleted_at IS NULL AND status = 'published' ORDER BY order_index, id",
                event["id"], job["stand_id"],
            )
        else:
            stunt_rows = await conn.fetch(
                "SELECT * FROM stunts WHERE event_id = $1 AND deleted_at IS NULL"
                " AND status = 'published' ORDER BY order_index, id",
                event["id"],
            )
        stunts = [dict(r) for r in stunt_rows]

        palette_ids = sorted({
            int(s[k]) for s in stunts for k in ("palette_a_id", "palette_b_id") if s.get(k)
        })
        palettes = []
        for pid in palette_ids:
            palette = await conn.fetchrow(
                "SELECT id, name FROM palettes WHERE id = $1 AND deleted_at IS NULL", pid,
            )
            if not palette:
                continue
            colors = await conn.fetch(
                "SELECT id, code, name_th, hex, text_color FROM palette_colors"
                " WHERE palette_id = $1 AND deleted_at IS NULL ORDER BY order_index, id",
                pid,
            )
            palettes.append({
                "id": palette["id"], "name": palette["name"],
                "colors": [dict(c) for c in colors],
            })

        roster_rows = await conn.fetch(
            "SELECT stand_id, row_index, col_index, row_label, seat_label, student_code, student_name"
            " FROM seat_rosters WHERE event_id = $1 AND deleted_at IS NULL"
            " ORDER BY stand_id, row_index, col_index",
            event["id"],
        )
        rosters = [dict(r) for r in roster_rows]

    return {"event": event, "stands": stands, "palettes": palettes,
            "stunts": stunts, "rosters": rosters}
