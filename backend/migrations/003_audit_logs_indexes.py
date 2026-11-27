"""
Migration 003 — Indexes ของ audit_logs (หน้า admin ดูประวัติ + keyset pagination)

- (created_at DESC, id DESC) → keyset cursor (หน้าใหม่แทรกหัวตลอด — ห้าม OFFSET)
- (action, created_at DESC) → กรองตาม action
- (entity_type, entity_id) → ดูประวัติของ entity หนึ่ง
- (user_id, created_at DESC) → ดูประวัติของ user คนเดียว
"""
VERSION = "003_audit_logs_indexes"
DESCRIPTION = "indexes ของ audit_logs (keyset + filter)"


async def upgrade(conn) -> None:
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_created_id ON audit_logs(created_at DESC, id DESC)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_action_created ON audit_logs(action, created_at DESC)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_user_created ON audit_logs(user_id, created_at DESC)"
    )
