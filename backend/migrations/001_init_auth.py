VERSION = "001_init_auth"
DESCRIPTION = "index ตาม role ของผู้ใช้ (soft delete)"


async def upgrade(conn) -> None:
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role) WHERE deleted_at IS NULL"
    )
