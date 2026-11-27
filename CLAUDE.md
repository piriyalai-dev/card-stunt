# CLAUDE.md — Pixel Stand (card-stunt)

ระบบแปรอักษรกีฬาสี · FastAPI + Vue 3 · template มาจาก `prsc_portal` (KEEP โครงสร้าง / ADAPT ชื่อ / DROP domain)

## Layer (backend — กฎตายตัว)

`routers/` (thin: parse Pydantic + `Depends` + map exception→HTTP) → `services/` (business logic, `pool` arg แรก,
`async with pool.acquire()` + `conn.transaction()`, raise domain exception) → raw asyncpg · `models/` = Pydantic เท่านั้น
**ไม่มี ORM** · backend เท่านั้นที่แตะ DB

## จุดต่างจาก prsc_portal (สำคัญ)

- **single environment** — ไม่มี `ENV_NAME` multi-env: image/stack/volume/network ใช้ prefix คงที่ `pixelstand`
- **role อยู่บน `users`** (`users.role`) — ไม่มีตาราง `students`/`rooms` (3 บทบาท admin/designer/staff ไม่มีห้อง/ระดับชั้น)
- **RBAC** ใน `core/rbac.py` → `require_permission(conn, user_id, perm)` อ่าน `config/roles.json`
- **มีแล้ว**: ARQ export worker (PDF/CSV/ZIP), signed media URL, audit_logs + SSE live sync (Phase 3/5)

## คำสั่ง

```bash
docker compose -f docker-compose.test.yml run --rm test_runner   # backend tests
cd frontend && npm run type-check && npm run lint && npm run test:unit && npm run test:e2e && npm run build
```

## Naming (locked)

| | ค่า |
|---|---|
| stacks / images | `pixelstand_infra` `pixelstand_app` / `pixelstand-backend` `pixelstand-frontend` |
| internal net | `pixelstand-internal` |
| DB / user / redis db | `pixelstand_db` / `pixelstand` / `1` |
| ARQ queue / PG NOTIFY | `pixelstand:queue:export` / `pixelstand_live` (Phase 3/5) |
| test pg port | `5436` |

## Phase status

Phase 2 (scaffold) เสร็จ · Phase 3 (Backend Core) เสร็จ · Phase 4 (Frontend Admin + Engine) เสร็จ ·
**Phase 5 (Viewer PWA + ARQ Export + Media + Docs + Playwright E2E) เสร็จ** · เหลือ deploy swarm จริง

## Frontend (Phase 4) — สิ่งที่ควรรู้ก่อนแก้

- **Route ผูกกับ event:** `/admin/events/:eventId/{stands,palettes,stunts}` อยู่ใน `EventWorkspace` (แท็บ + `provide/inject` event context)
  · Studio/Converter อยู่นอก workspace: `/admin/stunts/:stuntId/{studio,convert}` (โหลด stunt/stand/palettes เอง)
- **Engine เป็น pure modules ใน `frontend/src/lib/`** — `geometry` (ตรง `core/grid.py`), `color` (CIELAB/ΔE2000/WCAG),
  `grid` (typed array, RLE, undo diff, region), `quantize` (ปรับภาพ + dither), `crop`, `renderer` — เทสต์ใน `src/__tests__/`
- **Canvas:** 1 px/ช่อง → `ImageData` → `drawImage` nearest-neighbor · **ห้าม** วาด `fillRect` ต่อช่องหรือ `v-for` div
  (250×400 = 100k ช่อง ยัง ~60fps) · grid เก็บ `Int32Array` โดย `-1 = ว่าง`, แปลง null ที่ขอบ API
- **Undo = diff** (`GridChange`) 60 ขั้น · draft autosave RLE ใน localStorage (`pixelstand:draft:{id}`)
  · converter ส่งผลผ่าน `sessionStorage` key `pixelstand:pending-import:{id}` แล้ว Studio ดันเป็น 1 undo step
- **FormData upload:** axios instance ตั้ง `Content-Type: application/json` ⇒ ต้องส่ง `headers: { 'Content-Type': 'multipart/form-data' }`
  ไม่งั้น axios จะ `JSON.stringify(FormData)` และ backend ตอบ 422 (เจอจริงกับ reference image)
- **Grid เต็มไม่ได้อยู่ใน `StuntOut`** — ใช้ `GET /stunts/{id}/grid` / `PUT /stunts/{id}/grid` เท่านั้น (payload ~1MB)

## Phase 5 (เสร็จ) — สิ่งที่ควรรู้ก่อนแก้

- **Viewer PWA** `/e/:slug?` อยู่นอก MainLayout · `StudentViewer` = picker → cue list → focus
  · component ใน `components/viewer/` · helper pure functions ใน `lib/seatView.ts`
  · cache offline ใน `localStorage` (`services/publicCache.ts`) — **ห้าม cache `/api` ใน `sw.js`**
  · manifest `start_url=/e` ⇒ เปิดจาก home screen กลับงานล่าสุด
- **Public API ต้องไม่ใช้ axios instance ของ admin** — `services/publicApi.ts` ใช้ `fetch`
  (interceptor 401 ของ admin จะเด้งผู้ชมออกจากหน้าโฟกัส)
- **Media:** `GET /api/v1/stunts/{id}/media-urls` → signed URL (HMAC, ~15 นาที)
  · `<img>`/overlay ต้องตั้ง `crossOrigin='anonymous'` ก่อน `src` ไม่งั้น canvas taint
- **Export:** `POST /events/{id}/exports` → ARQ `generate_export` → `workers/export_worker.py`
  · builder pure functions ใน `services/export_builders.py` (PDF ใช้ Pillow+Raqm ไม่ใช่ reportlab)
  · compose มี service `worker` (image เดียวกับ backend) + volume `pixelstand_export_data`
- **Admin tabs:** `event-live` (`CONTROL_LIVE`) + `event-exports` (`EXPORT`) ใน `EventWorkspace`
- **E2E:** Playwright mock API (`frontend/e2e/`) — `npm run test:e2e` ไม่ต้องมี backend
