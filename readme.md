# Pixel Stand — ระบบแปรอักษรกีฬาสี

แปลงรูปจริงเป็นพิกเซล → วาด/แก้บน Canvas → เผยแพร่โพยให้นักเรียน 500–1,500 คนเปิดดูบนมือถือกลางสนาม
(design report: `~/reports/card-stunt-design-report.html`)

**สถานะ: Phase 3 — Backend Core** (schema + RBAC + domain APIs + Redis cache + SSE live sync · ยังไม่ deploy ลง Swarm)

## โครงสร้าง

```
card-stunt/
├── backend/   FastAPI + raw asyncpg (routers → services → models) · ไม่มี ORM
├── frontend/  Vue 3 + Vite + Tailwind (admin SPA + student PWA ใน SPA เดียว)
├── docker-compose.{infra,app,proxy,test}.yml
├── docs/      rules/ + 4 book folders (Phase 5)
└── ops/backup/
```

## Setup / Deploy (Swarm)

```bash
cp .env.example .env          # แล้วแก้ POSTGRES_PASSWORD / API_KEY / SECRET_KEY / JWT_SECRET
./setup.sh                    # swarm + network + infra (db/redis) + build + deploy pixelstand_app
./pull_all.sh                 # อัปเดตโค้ดล่าสุด (reset + build + zero-downtime deploy)
./rollback.sh <tag>           # ถอย image (ไม่แตะ git)
```

## Test

```bash
# backend (Postgres จริง + Redis + pytest)
docker compose -f docker-compose.test.yml up -d test_db test_redis
docker compose -f docker-compose.test.yml run --rm test_runner

# frontend (4 ขั้น)
cd frontend && npm install
npm run type-check && npm run lint && npm run test:unit && npm run build
```

## Dev

```bash
cd backend && pip install -r requirements.txt && uvicorn main:app --reload   # :8000
cd frontend && npm run dev                                                   # :5173
```

## Naming (single environment — ไม่มี ENV_NAME แบบ prsc)

| | ค่า |
|---|---|
| stacks | `pixelstand_infra` / `pixelstand_app` |
| images | `pixelstand-backend` / `pixelstand-frontend` |
| internal net | `pixelstand-internal` |
| DB / user / redis db | `pixelstand_db` / `pixelstand` / `1` |
| ARQ queue / PG NOTIFY | `pixelstand:queue:export` / `pixelstand_live` |
| test pg port | `5436` |

## API (Phase 3 — prefix `/api/v1`)

- Auth/Users: `/auth/*`, `/users`
- Domain: `/events` (+ nested `/stands`, `/palettes`, `/stunts`, `/rosters`, `/exports`), `/stands/{id}/resize|blocked-seats`, `/stunts/{id}/grid|revisions|reference-image`, `/palettes/{id}/colors`
- Live: `POST /events/{id}/live/advance`
- Public (ไม่ auth): `/public/events/{slug}/{meta|seat|version|live}`
- Admin: `/audit-logs`, `/version`

## Deploy ลง Swarm

```bash
./setup.sh   # ทำทุกอย่าง (swarm + network + infra + build + deploy)
```

Traefik (`global_proxy`) ที่แชร์อยู่บนเครื่อง route `pixel.singto1597.xyz` (เครื่องนี้) ตาม labels ใน `docker-compose.app.yml`
(ยัง HTTP — HTTPS / ACME ตาม design report §12 "ใช้ HTTP ก่อน"; `pixel.pirivoice.com` จะไปทำบนเซิร์ฟเวอร์ pirivoice ทีหลัง)

Traefik (`global_proxy`) ที่แชร์อยู่บนเครื่องจะ route `pixel.singto1597.xyz` (เครื่องนี้) ตาม labels ใน `docker-compose.app.yml`
(ยัง HTTP — HTTPS / ACME ตาม design report §12 "ใช้ HTTP ก่อน"; `pixel.pirivoice.com` จะไปทำบนเซิร์ฟเวอร์ pirivoice ทีหลัง)
