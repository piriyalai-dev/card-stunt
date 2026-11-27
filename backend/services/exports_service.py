import asyncpg

from core.exceptions import ConflictError, NotFoundError, ValidationError
from core.logger import AuditLogger
from core.rbac import require_permission

EXPORT_COLS = "id, event_id, stand_id, format, scope, status, file_path, error, requested_by, created_at, completed_at"


async def create_export(pool: asyncpg.Pool, actor_id: int, event_id: int, data: dict) -> dict:
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
            return dict(await conn.fetchrow(f"SELECT {EXPORT_COLS} FROM export_jobs WHERE id = $1", jid))


async def get_export(pool: asyncpg.Pool, job_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(f"SELECT {EXPORT_COLS} FROM export_jobs WHERE id = $1", job_id)
        if not row:
            raise NotFoundError("ไม่พบ export job")
        return dict(row)


async def download_export(pool: asyncpg.Pool, job_id: int):
    """คืน path ของไฟล์ — Phase 5 ARQ เขียนไฟล์จริง; ตอนนี้ยังไม่มี → ConflictError."""
    job = await get_export(pool, job_id)
    if job["status"] != "done" or not job["file_path"]:
        raise ConflictError("export ยังไม่เสร็จ (รอ Phase 5 worker)")
    return job["file_path"]
