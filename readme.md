# Pixel Stand — ระบบแปรอักษรกีฬาสี

แปลงรูปจริงเป็นพิกเซล → วาด/แก้บน Canvas → เผยแพร่โพยให้นักเรียน 500–1,500 คนเปิดดูบนมือถือกลางสนาม
(design report: `~/reports/card-stunt-design-report.html`)

**สถานะ: Phase 2 — Scaffold & Infra** (auth + test harness เขียว · ยังไม่ deploy ลง Swarm)

## โครงสร้าง

```
card-stunt/
├── backend/   FastAPI + raw asyncpg (routers → services → models) · ไม่มี ORM
├── frontend/  Vue 3 + Vite + Tailwind (admin SPA + student PWA ใน SPA เดียว)
├── docker-compose.{infra,app,proxy,test}.yml
├── docs/      rules/ + 4 book folders (Phase 5)
└── ops/backup/
```

## Setup (local — Phase 2)

```bash
cp .env.example .env   # แล้วแก้ POSTGRES_PASSWORD / API_KEY / SECRET_KEY / JWT_SECRET
./setup.sh             # ตรวจ compose syntax + รัน backend tests
```

## Test

```bash
# backend (Postgres จริง + pytest)
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
| DB / user | `pixelstand_db` / `pixelstand` |
| test pg port | `5436` |

## Deploy ลง Swarm (Phase 5)

```bash
docker network create -d overlay --attachable pixelstand-internal
docker stack deploy -c docker-compose.infra.yml pixelstand_infra
IMAGE_TAG=$(git rev-parse --short HEAD) docker stack deploy -c docker-compose.app.yml pixelstand_app
```

Traefik (`global_proxy`) ที่แชร์อยู่บนเครื่องจะ route `pixel.singto1597.xyz` (เครื่องนี้) ตาม labels ใน `docker-compose.app.yml`
(ยัง HTTP — HTTPS / ACME ตาม design report §12 "ใช้ HTTP ก่อน"; `pixel.pirivoice.com` จะไปทำบนเซิร์ฟเวอร์ pirivoice ทีหลัง)
