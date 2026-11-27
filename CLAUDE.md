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
- **ยังไม่มี**: ARQ export worker (Phase 5), media/signed-URL (Phase 5) — audit_logs + SSE live sync มีแล้ว (Phase 3)

## คำสั่ง

```bash
docker compose -f docker-compose.test.yml run --rm test_runner   # backend tests
cd frontend && npm run type-check && npm run lint && npm run test:unit && npm run build
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

Phase 2 (scaffold) เสร็จ · Phase 3 (Backend Core) เสร็จ · Phase 4 Frontend Admin + Engine · Phase 5 Viewer PWA + Export + Deploy Swarm
