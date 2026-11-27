# Developer Playbook — Pixel Stand

> อ่าน `CLAUDE.md` ที่ root ก่อน — ที่นี่คือภาพรวมสำหรับคนใหม่ + ส่วน Phase 5

## Architecture

```
frontend (Vue 3 + Vite)
  /admin/*  ──axios(JWT)──┐
  /e/:slug  ──fetch(public)┤
                          ▼
                 backend (FastAPI)
                 routers → services → asyncpg
                          │
        ┌─────────────────┼──────────────────┐
        ▼                 ▼                  ▼
    PostgreSQL         Redis            /data/media
    (+ LISTEN/NOTIFY)  (cache + ARQ)    /data/exports
                          ▲
                          │
                    worker (ARQ)
                    workers/export_worker.py
```

- **single environment** — stack/image/volume prefix `pixelstand` (ไม่มี ENV_NAME)
- backend ไม่มี ORM · SQL อยู่ใน `services/` เท่านั้น · router map exception → HTTP
- public endpoints มี Redis cache + ETag (`core/cache.py`) — mutation bump `events.version`

## Phase 5 ที่เพิ่มเข้ามา

### 1. Media signed URL (`core/media.py`, `routers/media_router.py`)
- `<img src>` แนบ Bearer ไม่ได้ ⇒ ใช้โทเคน HMAC สั้น (`SECRET_KEY`, path + exp)
- `GET /api/v1/stunts/{id}/media-urls` คืน URL ของ reference/thumbnail
- client ต้องตั้ง `img.crossOrigin = 'anonymous'` **ก่อน** `src` ถ้าจะวาดลง canvas

### 2. ARQ export worker (`workers/export_worker.py`, `services/export_builders.py`)
- `POST /events/{id}/exports` → insert `export_jobs` → enqueue `generate_export`
- worker `max_jobs=1` → builder (pure functions) → เขียนไฟล์ → อัปเดต status
- **PDF ใช้ Pillow ไม่ใช่ reportlab** เพราะต้อง text shaping ไทย (Raqm) — ฟอนต์อยู่ที่ `backend/assets/fonts/`
- ไฟล์: `EXPORT_STORAGE_DIR/exports/<job_id>/export.<ext>` · `file_path` เก็บ relative
- ถ้า Redis ล่ม job ค้าง `queued` → `POST /exports/{id}/retry` เพื่อ requeue

### 3. Student viewer (`frontend/src/views/viewer/`, `components/viewer/`)
- `StudentViewer` = picker → list → focus · ข้อมูล cache ใน `localStorage` (`services/publicCache.ts`)
- ⛔ ไม่ cache `/api` ใน service worker (กฏใน `public/sw.js`)
- SSE live: `subscribeLive()` — เป็น of enhancement; UI ต้องทำงานได้เมื่อหลุด
- wake lock: `lib/wakeLock.ts` (ขอใหม่บน `visibilitychange`)

### 4. Staff tools
- `ExportCenter.vue` — roster import + export jobs + poll
- `LiveControl.vue` — next/prev/goto (`GET /events/{id}/live` ต้อง `CONTROL_LIVE`)

## Commands

```bash
# backend tests (Postgres/Redis ของ test harness)
docker compose -f docker-compose.test.yml up -d test_db test_redis
docker compose -f docker-compose.test.yml run --rm test_runner

# frontend gates (ต้องผ่านครบ)
cd frontend && npm run type-check && npm run lint && npm run test:unit && npm run build

# E2E (mock API — ไม่ต้องมี backend)
cd frontend && npm run test:e2e
```

> ⚠️ บนเครื่องนี้ docker build ไม่มี DNS — verify บน host ด้วย `backend/.venv` ตาม memory
> (`Docker env gotcha`) จนกว่า `/etc/docker/daemon.json` จะถูกแก้

## Testing conventions

- backend: `pytest` + `pytest-asyncio` · fixtures ใน `tests/conftest.py` (DB สุ่มชื่อ, TRUNCATE ก่อนทุก test)
- viewer helpers เป็น pure functions ใน `lib/seatView.ts` — เทสต์ใน `src/__tests__/seatView.spec.ts`
- export builders ทดสอบผ่าน worker lifecycle จริง (`tests/test_exports_worker.py`) ไม่ mock DB

## Deploy notes (Swarm)

`docker-compose.app.yml` มี 3 service: `backend`, `worker`, `frontend`
- backend และ worker ใช้ image เดียวกัน (`pixelstand-backend`), worker override command
- volume ที่ต้องคงอยู่: `media_data`, `export_data`
- worker ไม่มี healthcheck HTTP — ใช้ `restart_policy: on-failure`
- หลัง redeploy ตรวจ `docker service ps pixelstand_app_worker` ว่าไม่ restart loop
