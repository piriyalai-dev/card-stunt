"""
👷 ARQ export worker — รันเป็น service แยกใน stack เดียวกับ backend

    python -m workers.export_worker

⚠️ **max_jobs = 1** — export แต่ละงานใช้ RAM (PDF เป็นภาพ A4) และเขียนไฟล์ลง volume
   ⇒ ทำทีละงานปลอดภัยกว่าและคาดเดาหน่วยความจำได้ (design §5: worker แยกคิวต่อหน้าที่)

⚠️ Worker เรียก `init_db` ตอน startup ด้วย (advisory lock กันชนกับ backend)
   ⇒ ถ้า backend ยังไม่ขึ้นแต่ worker ขึ้นก่อน ก็ไม่พัง
"""
import asyncpg
from arq import cron, run_worker
from arq.connections import RedisSettings

from core.config import settings
from core.init_db import init_db
from services import exports_service


async def generate_export(ctx: dict, job_id: int) -> None:
    """ARQ task — งานเดียวที่ worker นี้รองรับตอนนี้."""
    await exports_service.run_export(ctx["pool"], int(job_id))


async def purge_exports(ctx: dict) -> int:
    """ลบไฟล์ export เก่าตาม retention (รันวันละครั้งตอนตี 3:17)"""
    return await exports_service.purge_expired_exports(ctx["pool"])


async def startup(ctx: dict) -> None:
    ctx["pool"] = await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=5)
    await init_db(ctx["pool"])


async def shutdown(ctx: dict) -> None:
    if ctx.get("pool"):
        await ctx["pool"].close()


def _redis_settings() -> RedisSettings:
    if settings.REDIS_URL:
        return RedisSettings.from_dsn(settings.REDIS_URL)
    return RedisSettings()


class WorkerSettings:
    functions = [generate_export]
    cron_jobs = [cron(purge_exports, hour=3, minute=17)]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _redis_settings()
    max_jobs = 1
    job_timeout = 600
    keep_result = 3600
    health_check_interval = 30


if __name__ == "__main__":
    run_worker(WorkerSettings)
