# Backend Rules (card-stunt)

## Layer ที่ห้ามข้าม

`routers` → `services` → raw asyncpg (ไม่มี ORM) · `models/` = Pydantic request/response เท่านั้น
routers ไม่เขียน SQL · services ไม่แตะ HTTP (รับ `pool` เป็น arg แรก)

- **ตัวตนมาจาก token เท่านั้น** — ห้ามเชื่อ `user_id`/`role` ที่ client ส่งมาใน body/query/header
  · router ดึง `user_ctx["user_id"]` จาก `get_current_user` แล้วโยนเข้า service (`ensure_user`)

## SQL

- parametrize `$1..$n` เสมอ — **ห้าม** string interpolation กับค่า
- soft delete บังคับ (`deleted_at IS NULL` ในทุก query ที่อ่าน) — ลืมที่ไหน = ข้อมูลที่ลบแล้วโผล่กลับมา
- JSONB เขียนด้วย `json.dumps(...)` / อ่าน guard `json.loads` (asyncpg อาจคืน `str`)
- partial unique index (`WHERE deleted_at IS NULL`) กันซ้ำเฉพาะแถว active
- **อ่าน-แล้ว-เขียน** ที่แข่งกันได้ (นับโควตา / เลื่อนคิว) → `SELECT ... FOR UPDATE` ใน transaction เดียว
- list ยาว ๆ → pagination / `LIMIT` ห้ามดึงทั้งตาราง
- dynamic PATCH → `req.model_dump(exclude_unset=True)` กันค่า `None` ทับของเดิม

## Auth / RBAC

- `get_current_user` (JWT `user_id` claim) → `{"user_id", ...}`
- permission ตรวจใน service ด้วย `require_permission(conn, user_id, perm)` (จาก `core/rbac.py`)
- 3 roles (admin/designer/staff) + ~10 perms อยู่ใน `config/roles.json` — แหล่งความจริงเดียว

## Router / Error

- ทุก endpoint ใส่ `response_model=` (กรองฟิลด์ลับ) — ยกเว้น file download / SSE / 204 ให้เขียนคอมเมนต์บอกเหตุผล
- service raise domain exception จาก `core.exceptions` → router แปลงด้วย `map_err` (`routers/_common.py`):

| Domain exception | HTTP |
|---|---|
| `NotFoundError` | 404 |
| `ForbiddenError` | 403 |
| `ValidationError` | 400 |
| `ConflictError` | 409 |
| `PayloadTooLargeError` | 413 |
| `RateLimitError` | 429 |
| `ServiceUnavailableError` | 503 |

> ⚠️ `ValidationError` ของ service = 400 แต่ของ Pydantic/FastAPI = 422 — คนละตัว อย่าสลับ

## Audit

- mutation (CREATE/UPDATE/DELETE) → `AuditLogger("<service>").log(...)` **ใน transaction เดียวกับข้อมูลหลัก**
  (เขียนนอก transaction = log หายได้ตอนข้อมูลหลัก rollback)
- context (ip/user_agent/trace_id/execution_time) มาจาก middleware — service ส่งแค่
  `action`/`entity_type`/`entity_id`/`old_values`/`new_values` + `actor_identifier`/`client_source`

## Migration

- `migrations/NNN_short_snake.py` — `VERSION` / `DESCRIPTION` / `async def upgrade(conn)`
- runner (`core/migrations.py`) ใช้ `pg_advisory_xact_lock` + ตาราง `schema_migrations`
- schema ฐานอยู่ใน `core/init_db.py` (mirror) · พฤติกรรม/trigger อยู่ที่ migration เท่านั้น

## Coding

- snake_case ตัวแปร/ฟังก์ชัน · PascalCase class · type hint ครบทั้ง param และ return
- เวลา = `Asia/Bangkok` (UTC+7) เสมอ

## Test

เพิ่มตารางใหม่ → เพิ่มชื่อใน `tests/conftest.py::_TABLES` ที่เดียว (ใช้ทั้ง TRUNCATE + เช็ค schema)
