"""
005 — `users.token_version` (revoke ทุก session ของ user ได้ทันที)

- access/refresh token ฝัง `ver` claim = token_version ณ ตอนออก token
- bump `token_version` (เปลี่ยนรหัส / logout-all) ⇒ token เก่าทั้งหมด (access + refresh)
  ใช้ไม่ได้ทันที แม้ยังไม่หมดอายุ — แก้จุดอ่อน "token อายุ 30 วัน revoke ไม่ได้"
"""
VERSION = "005_token_version"
DESCRIPTION = "เพิ่ม users.token_version สำหรับ revoke ทุก session"


async def upgrade(conn) -> None:
    await conn.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INT NOT NULL DEFAULT 0"
    )
