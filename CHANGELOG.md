# Changelog

## [Unreleased] — Deploy wiring: CORS + Redis + media volume

### Deploy wiring (2026-11-28)

- Backend: `CORS_ORIGINS` (config/env) แทน hardcode localhost — frontend ที่ `pixel.singto1597.xyz` เรียก API `api.pixel.singto1597.xyz` ได้
- Compose: backend `REDIS_URL` ชี้ `pixelstand_infra_redis:6379/1` ใน container + named volume `pixelstand_media_data` สำหรับ reference image
- Dockerfile: สร้าง `/data/media` เป็นของ `appuser` (named volume สืบทอด ownership)
- Tests: pytest preflight CORS (prod/dev ผ่าน, origin แปลกปลอมไม่ผ่าน)

**Migration:** ไม่มี migration ใหม่ — เตรียมความพร้อม deploy เท่านั้น

## [0.3.0] — 2026-11-28 — Phase 4 Frontend Admin + Engine

### Phase 4 — Frontend Admin + Engine (2026-11-27)

- Frontend: แดชบอร์ดงานจริง + Event Workspace (แท็บภาพรวม/แสตน/ชุดสี/ฉาก) + RBAC ตาม permission
- Stand Configurator: ตั้งค่าแถว/ที่นั่ง/ช่องย่อย/ทิศทาง/ป้าย + ผังคลิก-ลากมาร์กช่องบันได + ปรับขนาดพร้อมเตือน crop
- Palette Manager: CRUD ชุดสี/สี · auto-contrast ตัวอักษร · เรียงลำดับ · preset 12 สี · import/export JSON · ลบสีพร้อมสีทดแทน
- Stunt Manager: สร้าง/แก้/ทำสำเนา/ลบ/เรียง (drag + ปุ่ม) · กลุ่มตาม section · publish
- Image-to-Pixel: crop ล็อกอัตราส่วน · rotate/flip · brightness/contrast/saturation/sharpness · CIELAB ΔE2000 · dither (none/FS/Bayer) · despeckle · ส่งเข้า Studio เป็น 1 undo step
- Pixel Studio: canvas หลายชั้น + typed array · brush/eraser/bucket/eyedropper/shapes/text/select-move-copy-paste · nudge · undo/redo 60 ขั้น · pan/zoom · ภาพอ้างอิง · autosave draft · revisions · distance mode · ด้าน A/B
- Backend: `GET /api/v1/stunts/{id}/grid` (โหลด grid เต็มสำหรับ Studio) · แก้ `GET /stunts/{id}/stats` ที่เคย 500 (อ่าน grid_data จาก query ที่ไม่ได้ select)
- Tests: frontend vitest 78 (geometry/color CIEDE2000 อ้างอิง Sharma/grid/quantize/crop + สเกล 250×400 = 100,000 ช่อง) · backend pytest 68

**Migration:** ไม่มี migration ใหม่ — schema เดิมจาก Phase 3 (เพิ่มเฉพาะ endpoint `GET /stunts/{id}/grid` และแก้บั๊ก stats)

## [0.2.0] — 2026-11-27 — Phase 3 Backend Core

- Backend: schema 9 ตาราง (events/stands/palettes/palette_colors/stunts/stunt_revisions/seat_rosters/export_jobs/audit_logs) + RBAC + domain APIs ครบตาม design §7
- Public: `/api/v1/public/*` meta/seat/version + Redis cache/ETag
- Live Sync: SSE + PG NOTIFY channel `pixelstand_live`
- Workflow: mirror pirivoice (pull_all/setup/rollback/release/CI/version-manifest/ops backup) + prefix `/api/v1`

**Migration:** `002_domain_indexes` · `003_audit_logs_indexes` · `004_live_sync_notify`

## [0.1.0] — 2026-11-27 — Phase 2 scaffold

- Backend: auth (login / me / change-password) + RBAC 3 roles + test harness
- Frontend: design system + login + admin shell (MainLayout) + route trees (`/admin/*` + `/e/:slug`)
- Infra: 4 docker-compose (infra / app / proxy / test) · `.env.example` · setup.sh

**Migration:** `001_init_auth` — DB schema เริ่มจาก `core/init_db.py` (users)

[Unreleased]: https://github.com/piriyalai-dev/card-stunt/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/piriyalai-dev/card-stunt/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/piriyalai-dev/card-stunt/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/piriyalai-dev/card-stunt/compare/84bf061...v0.1.0
