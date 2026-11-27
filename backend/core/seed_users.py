"""Seed ผู้ใช้เริ่มต้น (admin / designer / staff) ตอนเปิดระบบครั้งแรก — idempotent.

username เดายาก + รหัสชั่วคราว + `must_change_password = TRUE` (บังคับเปลี่ยนตอน login ครั้งแรก)
ข้อมูลถูกพิมพ์ที่ log และเขียนลงไฟล์ (SEED_CREDENTIALS_FILE)
"""
import asyncio
import logging
import os
import secrets
import string

import asyncpg

from core.config import settings
from services.auth_service import hash_password

logger = logging.getLogger("API_SEED_USERS")

SEED_ROLES = [
    ("admin", "แอดมินระบบ"),
    ("designer", "นักออกแบบ"),
    ("staff", "สตาฟ"),
]


def _random_username(prefix: str) -> str:
    return f"pixel_{prefix}_{secrets.token_hex(3)}"


def _random_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_"
    safe = alphabet.replace("0", "").replace("O", "").replace("1", "").replace("l", "").replace("I", "")
    return "".join(secrets.choice(safe) for _ in range(length))


async def _has_users(pool: asyncpg.Pool) -> bool:
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT 1 FROM users WHERE deleted_at IS NULL LIMIT 1")


def _write_credentials_file(creds: dict) -> str:
    lines = [
        "Pixel Stand — บัญชีผู้ดูแลระบบที่สร้างอัตโนมัติ (เปิดระบบครั้งแรก)",
        "=" * 60,
        "⚠️ ระบบจะบังคับให้เปลี่ยนรหัสผ่านเมื่อเข้าสู่ระบบครั้งแรก",
        "โปรดเก็บไฟล์นี้ไว้ในที่ปลอดภัย และลบออกหลังเปลี่ยนรหัสผ่านครบแล้ว",
        "",
    ]
    for role, info in creds.items():
        lines.append(f"[{role}] ({info['display_name']})")
        lines.append(f"  Username : {info['username']}")
        lines.append(f"  Password : {info['password']}")
        lines.append("")

    path = os.path.abspath(settings.SEED_CREDENTIALS_FILE)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


async def seed_default_users(pool: asyncpg.Pool) -> dict:
    """สร้าง admin/designer/staff ถ้ายังไม่มีผู้ใช้เลย — idempotent."""
    if await _has_users(pool):
        logger.info("ℹ️ พบผู้ใช้อยู่แล้ว — ข้ามการ seed default users")
        return {}

    creds = {}
    async with pool.acquire() as conn:
        async with conn.transaction():
            for role, display_name in SEED_ROLES:
                username = _random_username(role)
                password = _random_password()
                await conn.execute(
                    "INSERT INTO users (username, password_hash, display_name, role, must_change_password)"
                    " VALUES ($1, $2, $3, $4, TRUE)",
                    username, hash_password(password), display_name, role,
                )
                creds[role] = {"username": username, "password": password, "display_name": display_name}

    path = _write_credentials_file(creds)
    logger.info("✅ สร้างบัญชีผู้ดูแลระบบเริ่มต้น (%d บัญชี) — เก็บไว้ที่ %s", len(creds), path)
    for role, info in creds.items():
        logger.info("   • [%s] username=%s", role, info["username"])
    return creds


if __name__ == "__main__":
    async def _main():
        p = await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=2)
        try:
            await seed_default_users(p)
        finally:
            await p.close()
    asyncio.run(_main())
