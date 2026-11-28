# Changelog

## [Unreleased] — ยังไม่ตัดเวอร์ชัน

## [0.5.0] — 2026-11-28 — Security & deploy hardening + JWT access/refresh + P3 features

### Fix — Wave 1 (บั๊ก + security) (2026-11-28)

- import roster: ปฏิเสธ `.xls` (BIFF/OLE ที่ openpyxl อ่านไม่ได้) → 400 ชัดเจนไม่ใช่ 500 · ตัด `.0` ของ `student_code` ที่ Excel เก็บเป็นตัวเลข
- `/health` คืน 503 เมื่อ DB ล่ม (เดิม 200 ปลอมทำให้ `curl -f` healthcheck เขียวทั้งที่ DB ตาย)
- auth: บังคับ `must_change_password` ฝั่ง server + token ของ user ที่ถูกลบใช้ต่อไม่ได้ (revalidate ต่อ DB ทุก request)
- export ZIP: เรนเดอร์ด้าน B (`stunts/*-b.png`) สำหรับแสตน 2 หน้า + ระบุ side ใน manifest
- `change_password` ลง audit log (action `CHANGE_PASSWORD`)
- rate limit login (per IP + username · Redis + in-memory fallback) — `LOGIN_RATE_LIMIT_MAX` / `LOGIN_RATE_LIMIT_WINDOW_SECONDS`
- ลบ dead auth code (`verify_api_key`, X-API-Key/`is_system` path ที่เป็นทางตัน)

**Migration:** ไม่มี migration ใหม่

### Fix — Wave 2 (security round 2) (2026-11-28)

- login ไม่ leak ว่า user มีจริงไหม (unify error message unknown-user ↔ wrong-password)
- password policy: รหัสผ่านใหม่ต้อง ≥8 ตัว + มีทั้งตัวอักษรและตัวเลข (change-password + create/update user)
- rate limit งาน bulk ต่อ user (upload reference image / import roster / สร้าง export) — `BULK_OP_RATE_LIMIT_MAX` / `BULK_OP_RATE_LIMIT_WINDOW_SECONDS`
- gateway body-size limit: ปฏิเสธ request ที่ body เกิน `MAX_REQUEST_BODY_MB` ด้วย 413 ก่อน buffer เข้า memory

**Migration:** ไม่มี migration ใหม่

### Chore — Wave 3 (deploy hardening) (2026-11-28)

- CI: workflow `ci-tests.yml` รัน backend pytest + frontend type-check/lint/unit/build + Playwright E2E (เดิม CI ทำแค่ version-manifest + `bash -n`)
- healthcheck: infra db (`pg_isready`) + redis (`redis-cli ping`) + frontend (nginx `wget`)
- `.env.example` ครบทุก Settings field ที่มีผล (JWT / cache TTL / media dimension / roster limits / seed file)
- docs: `production-hardening.md` — runbook สำหรับ HTTPS (แตะ shared traefik), Docker secrets, resource limits · เตรียม tls label (commented) ใน `docker-compose.app.yml`

**Migration:** ไม่มี migration ใหม่

### Fix — Wave 4 (JWT lifecycle: access + refresh) (2026-11-28)

- เปลี่ยนจาก access token เดียวอายุ 30 วันใน localStorage → **access token สั้น (15 นาที) ใน memory + refresh token (7 วัน) ใน httpOnly cookie** (`SameSite=Lax`)
- เพิ่ม `users.token_version` (migration 005) — bump ตอนเปลี่ยนรหัส ⇒ revoke ทุก session ทันที (access + refresh)
- endpoint ใหม่: `POST /auth/refresh` (ขอ access token ใหม่) · `POST /auth/logout` (ล้าง refresh cookie)
- `get_current_user` ตรวจ `type=access` + `ver` ตรง `token_version` (refresh token ใช้เป็น access ไม่ได้)
- frontend: token เก็บใน memory (`services/token.ts`) · axios `withCredentials` + 401 silent-refresh retry · router guard bootstrap · change-password หลัง revoke พา login ใหม่
- E2E: mock `POST /auth/refresh` (bootstrap)

**Migration:** `005_token_version` — เพิ่ม `users.token_version INT NOT NULL DEFAULT 0`

### Chore — Wave 5 (cleanup dead code) (2026-11-28)

- ลบ dead code: `core/cache.py` (`incr`/`delete`/`event_gen_key` ที่ไม่มีใครเรียก) · `core/queues.py` (`EXPORT_QUEUE` ไม่ถูกใช้ — enqueue/worker ใช้ job name `generate_export` ตรง ๆ) · `core/rbac.py::require_any_permission` · config `MAX_STAND_ROWS`/`MAX_STAND_COLS`/`MAX_SUB_SIZE` (ใช้จริงแค่ `MAX_TOTAL_CELLS`)
- รวม `UserOut` ที่ประกาศซ้ำ (`models/auth_schemas` + `models/user_schemas`) → ใช้ตัวเดียวจาก `user_schemas`
- `ExportCreate.scope` เป็น `Literal["event", "stand"]` (เดิม free-text) + tighten type ฝั่ง frontend (`services/exports.ts`, `types/domain.ts`)
- แก้ media orphan: `delete_stunt` ลบไฟล์ reference/thumb หลัง commit (เดิม `delete_stunt_files` ประกาศไว้แต่ไม่ถูกเรียก)
- setup.sh: ไม่สร้าง network `db-management` (เหลือจาก template classroom — pixelstand ใช้แค่ `pixelstand-internal` + `traefik-public`)
- ลบ dep `@vue/test-utils` (ไม่มี test ใช้) · แก้ stale comment/docstring ที่ระบุโปรเจกต์เป็น "PIRIvoice" (`core/migrations.py`, `vite.config.ts`)

**Migration:** ไม่มี migration ใหม่

### Feat — Wave 6 (docs port + P3 features) (2026-11-28)

#### Docs — ย้าย lessons + กฎจาก Pirivoice (กรองเอาเฉพาะของทั่วไป)

- `docs/skills.md` ใหม่: คลังบทเรียน **226 entries** จาก `prsc_portal/docs/skills.md` — ตัด domain เฉพาะ PIRIvoice 25 ตัว · แปลงตัวอย่าง domain ให้เป็นกลาง (rooms→lookup tables, issues→records) + ต่อท้ายด้วยบทเรียนเฉพาะ Pixel Stand (openpyxl `.xls` · Excel float `.0` · health 503 · JWT access+refresh+`token_version` · media orphan · login enumeration · docker no-DNS)
- `docs/rules/{backend,frontend,testing}.md` เสริมจาก Pirivoice: `FOR UPDATE` กัน race · `response_model` ทุก endpoint · error mapping ตาราง · audit ต้องใน transaction · "ว่าง ≠ พัง ≠ โหลดไม่เสร็จ" · deep DB verify · mock เฉพาะขอบ process · 400 vs 422 · กฎ "บันทึกบทเรียนลง skills.md"

#### P3 features

- **PWA install prompt**: `InstallPrompt.vue` (ชวนติดตั้ง + แจ้งเวอร์ชันใหม่ + iOS hint) ต่อกับ state machine ใน `pwa.ts` เดิม (เดิมมี logic ครบแต่ไม่มี component) — mount ที่ `App.vue`
- **จัดการผู้ใช้** (`MANAGE_USERS`): หน้า `/admin/users` + `services/users.ts` (สร้าง/แก้ role/ reset password/ลบ)
- **บันทึกการใช้งาน** (`VIEW_AUDIT_LOG`): หน้า `/admin/audit` + `services/audit.ts` (filter action/service/status/entity + ค้นหา + cursor pagination)
- **ดาวน์โหลด PNG ฉาก**: ปุ่มใน Pixel Studio — `lib/renderer.ts::exportGridPngDataUrl`
- **QR แชร์ลิงก์ผู้ชม**: `QrCode.vue` (lib `qrcode`) ใน EventOverview พร้อมคัดลอก/เปิดลิงก์

**Migration:** ไม่มี migration ใหม่

### Feat — Wave 7 (P5 deploy hardening) (2026-11-28)

- **Docker secrets**: ย้าย `POSTGRES_PASSWORD/API_KEY/SECRET_KEY/JWT_SECRET` ออกจาก env เป็น swarm secret — `core/config.py` เพิ่ม `_read_secret` + validator (`_secret_or_required`, `_inject_db_password`) · infra db ใช้ `POSTGRES_PASSWORD_FILE` · app backend/worker mount 4 secrets + `environment:` override ค่า sensitive เป็นว่าง · `setup.sh`/`pull_all.sh` สร้าง secret idempotent (`ensure_secret`)
- **Resource limits**: `deploy.resources.limits/reservations` ทั้ง 5 services (backend 1G · worker 2G · frontend 128M · db 1G · redis 256M)
- **Coverage**: test_runner รัน pytest `--cov=core --cov=services --cov=routers --cov=workers` (report ขึ้น CI log)
- test: `tests/test_config.py` — secret field ว่าง→error · URL password injection · URL ที่มี password ไม่ถูกแตะ

**Migration:** ไม่มี migration ใหม่

### Feat — Wave 8 (P6: quantize → Web Worker) (2026-11-28)

- ย้ายงาน CPU หนักตอนแปลงรูปเป็นพิกเซล (ปรับแสง + quantize ΔE2000 + despeckle) ออกจาก main thread
  ไป `src/workers/quantize.worker.ts` — UI ไม่กระตุกตอนแปลง (ImageConverter `compute()` ตอนนี้ `await runQuantize(...)`)
- worker รับ `Uint8ClampedArray` (transferable) → คืน `Grid` (Int32Array, transferable) · วาด canvas/`getImageData`
  ยังอยู่ main thread (ถูกมาก) เฉพาะ math หนักย้ายไป worker
- `skills.md`: บันทึกกับดัก `new URL(..., import.meta.url)` ใน Vue SFC (path สัมพัทธ์กับไฟล์ .vue ไม่ใช่ src/)

**ยังไม่ทำ (P6 ที่เหลือ — เหตุผล):** component test (ขัดปรัชญา pure-module testing — logic อยู่ใน `lib/` และ test แล้ว)
· list pagination (roster จำกัด `ROSTER_MAX_ROWS=5000` + frontend slice 200) · SSE multi-process (deploy เป็น single replica)

**Migration:** ไม่มี migration ใหม่

## [0.4.0] — 2026-11-28 — Phase 5 Viewer PWA + Export + Media (+ deploy hotfixes)

### Phase 5 — Student Viewer PWA (2026-11-27)

- `/e/:slug` → 3 โหมด: seat picker (dropdown + ผังแสตน + ค้นหาเลขประจำตัว) → cue list (ทุกฉาก + เพลท 5×5) → focus/show mode
- Focus mode: กล่องสีใหญ่ + รหัสยักษ์ + ชื่อสี · next-cue preview · ปัด/ลูกศร · jump ฉาก · Screen Wake Lock · ตามคิวสด (SSE) ปิดได้
- Offline-first: cache meta/seat/selection ใน `localStorage` · เปิดออฟไลน์กลางสนามได้ · เช็คเวอร์ชันทุก 60 วิ + ตอนกลับมา online
- PWA manifest `start_url=/e` (กลับงานล่าสุด) · หน้า `/e` ไม่มี slug เปิดจาก home screen ได้
- Public API: `GET /public/events/{slug}/seat?student_code=` (ต้องเปิด `roster_lookup_enabled`) · meta เพิ่มสี `id`, ทิศทางแสตน, notes
- ความเป็นส่วนตัว: `seat?row&col` แสดงชื่อนักเรียนเฉพาะเมื่อเปิด `roster_lookup_enabled`

### Phase 5 — ARQ export worker (2026-11-27)

- `POST /events/{id}/exports` → คิว `pixelstand:queue:export` → worker สร้าง PDF/CSV/ZIP
- PDF: การ์ดโพยรายที่นั่ง 4 ใบ/A4 (Pillow + Raqm shaping ฟอนต์ไทย `Noto Sans Thai`)
- CSV: ทุกที่นั่ง × ฉาก (ด้าน A/B · รหัสสีทั้ง 25 ช่อง) · ZIP: ภาพกริดทุกฉาก + `seats.csv` + `manifest.json`
- `GET /events/{id}/exports` · `GET /exports/{id}/download` (FileResponse) · `POST /exports/{id}/retry`
- Compose: service `worker` + volume `pixelstand_export_data` · `arq==0.26.3`

### Phase 5 — Media signed URL (2026-11-27)

- `GET /api/v1/stunts/{id}/media-urls` → HMAC-signed URL (path + exp, TTL 15 นาที)
- `GET /api/v1/media/<path>?exp=&sig=` — `<img>` ใช้ได้โดยไม่แนบ Bearer · กัน path traversal
- Pixel Studio โหลดภาพอ้างอิงที่บันทึกไว้กลับมาเป็น overlay (`crossOrigin=anonymous` กัน canvas taint)

### Phase 5 — Admin staff tools (2026-11-27)

- แท็บ `event-exports` (สิทธิ์ `EXPORT`): import รายชื่อ CSV/XLSX · ตารางค้นหา/ลบ · สร้าง export + poll สถานะ + ดาวน์โหลด/ลองใหม่
- แท็บ `event-live` (สิทธิ์ `CONTROL_LIVE`): next/prev/goto · รายการฉาก published + LIVE badge
- `GET /events/{id}/live` สำหรับหน้า admin (บังคับ `CONTROL_LIVE`)

### Phase 5 — Docs + Playwright E2E (2026-11-27)

- Docs 4 เล่ม: user guide · staff operations · admin guide · developer playbook
- Playwright (`frontend/e2e/`) mock API: viewer (เลือกที่นั่ง/ค้นหา/โฟกัส/ออฟไลน์) + export center (poll จนเสร็จ) + live control
- Tests: backend 88 · frontend vitest 91 · Playwright 5

### Fix (2026-11-28)

- `SUPER_ADMIN_ID=` (เว้นว่าง) เคยทำให้ `Settings()` โยน `ValidationError` ตอน import
  → backend container crash-loop ตอน deploy แรก · เพิ่ม validator แปลงค่าว่างเป็น `0`
  และปรับ `.env.example` เป็น `SUPER_ADMIN_ID=0`
- Tests: regression สำหรับค่าว่าง/ค่าปกติ + CORS default

### API domain (2026-11-28)

- เปลี่ยน API host → `pixel-api.singto1597.xyz` (traefik Host rule + `VITE_API_BASE_URL`)
  — frontend ต้อง rebuild เพราะ URL ถูก bake ลง bundle
- CORS ยังอนุญาต origin ของ frontend `https://pixel.singto1597.xyz` (ไม่เปลี่ยน)

**Migration:** ไม่มี migration ใหม่

## [0.3.2] — 2026-11-28 — Docker build context hygiene

### Build (2026-11-28)

- เพิ่ม `.dockerignore` ทั้ง backend/frontend — กัน host `.venv`, `node_modules`, cache เข้า build context
  (สำคัญ: native esbuild/rollup ของ host เป็น glibc จะทับตัว musl ของ Alpine แล้ว build frontend พัง)

**Migration:** ไม่มี migration ใหม่

## [0.3.1] — 2026-11-28 — Deploy wiring: CORS + Redis + media volume

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

[Unreleased]: https://github.com/piriyalai-dev/card-stunt/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/piriyalai-dev/card-stunt/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/piriyalai-dev/card-stunt/compare/v0.3.2...v0.4.0
[0.3.2]: https://github.com/piriyalai-dev/card-stunt/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/piriyalai-dev/card-stunt/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/piriyalai-dev/card-stunt/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/piriyalai-dev/card-stunt/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/piriyalai-dev/card-stunt/compare/84bf061...v0.1.0
