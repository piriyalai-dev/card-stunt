"""
purge_media.py — ลบไฟล์ reference/thumbnail ที่ soft-delete แล้ว / orphan เกินกำหนด

ลบ:
  1. ไฟล์ของ stunt ที่ deleted_at เกิน MEDIA_PURGE_AFTER_DAYS (default 30) → ลบแถว+ไฟล์
  2. ไฟล์ orphan ใน media dir ที่เก่ากว่า --orphan-age-hours (default 24)

dry-run เป็น default — ลบจริงต้อง --apply
"""
import argparse
import asyncio
import os
import time

import asyncpg

from core.config import settings

MEDIA_PURGE_AFTER_DAYS = 30


async def _purge(media_dir: str, apply: bool, orphan_age_hours: int) -> dict:
    pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=2)
    try:
        async with pool.acquire() as conn:
            # 1. stunts ที่ soft-delete เกินกำหนด
            rows = await conn.fetch(
                "SELECT id, reference_image_path, thumbnail_path FROM stunts"
                " WHERE deleted_at IS NOT NULL AND deleted_at < NOW() - $1::interval",
                f"{MEDIA_PURGE_AFTER_DAYS} days",
            )
            to_delete_files = []
            for r in rows:
                for col in ("reference_image_path", "thumbnail_path"):
                    if r[col]:
                        to_delete_files.append(os.path.normpath(r[col]))
                if apply:
                    await conn.execute("DELETE FROM stunts WHERE id = $1", r["id"])

            # 2. orphan files (ไม่ถูกอ้างโดยแถว active)
            refs = set()
            active = await conn.fetch(
                "SELECT reference_image_path, thumbnail_path FROM stunts WHERE deleted_at IS NULL"
            )
            for r in active:
                for col in ("reference_image_path", "thumbnail_path"):
                    if r[col]:
                        refs.add(os.path.normpath(r[col]))

            orphans = []
            for dirpath, _dirs, files in os.walk(media_dir):
                for f in files:
                    full = os.path.join(dirpath, f)
                    rel = os.path.normpath(os.path.relpath(full, media_dir))
                    if rel not in refs and (time.time() - os.path.getmtime(full)) > orphan_age_hours * 3600:
                        orphans.append(full)

            deleted = 0
            if apply:
                for full in to_delete_files:
                    p = os.path.join(media_dir, full)
                    if os.path.isfile(p):
                        os.remove(p); deleted += 1
                for full in orphans:
                    os.remove(full); deleted += 1

            return {"rows_deleted": len(rows) if apply else len(rows), "files": len(to_delete_files), "orphans": len(orphans), "deleted": deleted}
    finally:
        await pool.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--media-dir", default=settings.MEDIA_STORAGE_DIR)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--orphan-age-hours", type=int, default=24)
    args = ap.parse_args()

    r = asyncio.run(_purge(args.media_dir, args.apply, args.orphan_age_hours))
    mode = "ลบจริง" if args.apply else "dry-run"
    print(f"[{mode}] stunts ที่จะลบ: {r['rows_deleted']} · ไฟล์อ้าง: {r['files']} · orphan: {r['orphans']} · ลบไฟล์: {r['deleted']}")


if __name__ == "__main__":
    main()
