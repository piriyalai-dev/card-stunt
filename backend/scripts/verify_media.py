"""
verify_media.py — ตรวจความสอดคล้องระหว่าง DB (stunts.reference/thumbnail path) กับไฟล์ใน media dir

ใช้ผ่าน restore.sh (ซ้อมกู้) หรือรันมือ:
    python scripts/verify_media.py --media-dir /tmp/pixelstand-restore-xyz
(env: DATABASE_URL ต้องชี้ DB ที่จะตรวจ · --media-dir ชี้โฟลเดอร์ที่แตก media ออกมา)

ตรวจ:
  1. path ใน DB ที่ไม่มีไฟล์จริง (missing)
  2. ไฟล์ใน media dir ที่ไม่มีแถว DB อ้างถึง (orphan)
"""
import argparse
import asyncio
import os

import asyncpg

from core.config import settings


async def _verify(media_dir: str) -> dict:
    pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=2)
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, reference_image_path, thumbnail_path FROM stunts WHERE deleted_at IS NULL"
            )
        expected = set()
        for r in rows:
            for col in ("reference_image_path", "thumbnail_path"):
                p = r[col]
                if p:
                    expected.add(os.path.normpath(p))

        missing = []
        for p in sorted(expected):
            full = os.path.join(media_dir, p)
            if not os.path.isfile(full):
                missing.append(p)

        orphan = []
        for dirpath, _dirs, files in os.walk(media_dir):
            for f in files:
                rel = os.path.normpath(os.path.relpath(os.path.join(dirpath, f), media_dir))
                if rel not in expected:
                    orphan.append(rel)

        return {"expected": len(expected), "missing": missing, "orphan": orphan}
    finally:
        await pool.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--media-dir", required=True)
    args = ap.parse_args()

    result = asyncio.run(_verify(args.media_dir))
    print(f"ไฟล์ที่ DB อ้างถึง: {result['expected']}")
    if result["missing"]:
        print(f"❌ missing ({len(result['missing'])}):")
        for p in result["missing"]:
            print(f"   - {p}")
    else:
        print("✅ ไม่มีไฟล์ขาด")
    if result["orphan"]:
        print(f"⚠️ orphan ({len(result['orphan'])}):")
        for p in result["orphan"]:
            print(f"   - {p}")
    else:
        print("✅ ไม่มีไฟล์ orphan")
    if result["missing"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
