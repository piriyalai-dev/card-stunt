# เวอร์ชันและการปล่อยงาน

บทนี้ตอบว่าเลขเวอร์ชันของ Pixel Stand หมายถึงอะไร ใคร bump เมื่อไหร่
ปล่อยงานอย่างไรให้ย้อนดูได้ และถ้าปล่อยแล้วพังจะถอยกลับอย่างไร
(ลอกแบบ pirivoice — single env `pixelstand` ไม่มี staging/production แยก)

- 🔢 **SemVer** — MAJOR · MINOR · PATCH
- 🧾 **`CHANGELOG.md`** เขียนเป็นเรื่องเล่า ไม่ใช่รายการ Added/Changed/Fixed
- 🏷️ **annotated tag + GitHub Release ทุกเวอร์ชัน**
- 🔁 **`release.sh`** — ตรวจ · ตัด CHANGELOG · sync เลข · commit · tag · push · Release
- 🧪 **`release.sh --dry-run`** — ตรวจทุกด่านและดู diff โดยไม่แตะ git
- ⏪ **`rollback.sh <image-tag>`** — ถอย image โดยไม่แตะ git
- ✅ **CI + version manifest** (`ci-version.yml` + `scripts/version-manifest.mjs`)

## เลขเวอร์ชันอยู่ที่ไหน

| ไฟล์ | ค่า |
|---|---|
| `VERSION` | เลข SemVer ปัจจุบัน |
| `backend/core/config.py` | `PROJECT_VERSION` (ใช้ `/api/v1/version`) |
| `frontend/package.json` + `package-lock.json` | `version` + `packages[""].version` |
| `scripts/version-manifest.tsv` | ประวัติ cut commit ต่อเวอร์ชัน |

`version-manifest.mjs` ตรวจว่าทั้ง 4 ที่ + manifest + CHANGELOG + tag ตรงกันทั้งหมด

## ปล่อยรุ่นใหม่

```bash
# 1. เขียน CHANGELOG ใต้ [Unreleased] — ตั้งชื่อรุ่น + บรรทัด **Migration:**
# 2. ตรวจทุกด่าน (ไม่แตะ git)
./release.sh 0.2.0 --dry-run
# 3. ปล่อยจริง (commit + tag + push + GitHub Release)
./release.sh 0.2.0
```

- MAJOR = "วิธีคิดของระบบ" เปลี่ยน · MINOR = ฟีเจอร์/endpoint ใหม่ · PATCH = แก้บั๊ก/ปรับข้อความ
- `./release.sh 0.2.0-rc.1` = preview tag (ไม่แตะ CHANGELOG/VERSION)

## Rollback (image ไม่ใช่ git)

```bash
./rollback.sh --list          # ดู image tag ที่มี
./rollback.sh 9fbe3ad --dry-run
./rollback.sh 9fbe3ad         # สลับ image (checkout git ยังอยู่ที่เดิม)
```

## Bootstrap v0.1.0 (ทำครั้งเดียว ย้อนหลัง)

ไม่มี tag เก่า → `release.sh` หา tag ก่อนหน้าไม่เจอ ⇒ ต้องสร้าง v0.1.0 ย้อนหลังก่อน
(หรือปล่อยให้ 0.2.0 เป็น release แรกแล้ว backfill tag):

```bash
git tag -a v0.1.0 7569bc6 -m "v0.1.0 — 2026-11-27 — Phase 2 scaffold"
git push origin v0.1.0
```

## CI

`ci-version.yml` รัน `node scripts/version-manifest.mjs` + `bash -n` สคริปต์ deploy
ทุก push/PR เข้า `main` — fail = ประวัติเวอร์ชันไม่น่าเชื่อถือ (ห้ามปล่อย)
