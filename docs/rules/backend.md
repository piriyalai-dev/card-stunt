# Backend Rules (card-stunt)

## Layer ที่ห้ามข้าม

`routers` → `services` → raw asyncpg (ไม่มี ORM) · `models/` = Pydantic request/response เท่านั้น
routers ไม่เขียน SQL · services ไม่แตะ HTTP (รับ `pool` เป็น arg แรก)

## SQL

- parametrize `$1..$n` เสมอ — **ห้าม** string interpolation กับค่า
- soft delete บังคับ (`deleted_at IS NULL` ในทุก query)
- JSONB เขียนด้วย `json.dumps(...)` / อ่าน guard `json.loads` (asyncpg อาจคืน `str`)
- partial unique index (`WHERE deleted_at IS NULL`) กันซ้ำเฉพาะแถว active

## Auth / RBAC

- `get_current_user` (JWT `user_id` claim) → `{"user_id", "is_system"}`
- permission ตรวจใน service ด้วย `require_permission(conn, user_id, perm)` (จาก `core/rbac.py`)
- 3 roles (admin/designer/staff) + ~10 perms อยู่ใน `config/roles.json` — แหล่งความจริงเดียว

## Migration

- `migrations/NNN_short_snake.py` — `VERSION` / `DESCRIPTION` / `async def upgrade(conn)`
- runner (`core/migrations.py`) ใช้ `pg_advisory_xact_lock` + ตาราง `schema_migrations`
- schema ฐานอยู่ใน `core/init_db.py` (mirror) · พฤติกรรม/trigger อยู่ที่ migration เท่านั้น

## Test

เพิ่มตารางใหม่ → เพิ่มชื่อใน `tests/conftest.py::_TABLES` ที่เดียว (ใช้ทั้ง TRUNCATE + เช็ค schema)
