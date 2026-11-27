"""
Fixtures สำหรับ pytest integration tests ของ Pixel Stand.

Pattern ตาม prsc_portal:
- test_db_url: สร้าง DB ใหม่แบบสุ่มชื่อทุก session → init_db → drop ตอนจบ
- client: เปลี่ยน settings.DATABASE_URL ไปยัง test DB
- clean_database: ล้างตารางก่อนทุก test
"""
import os
import tempfile
import uuid
from urllib.parse import urlparse

import asyncpg
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from core.config import settings
from core.init_db import init_db
from main import app

# ไฟล์ credentials ของ seed users — ชี้ไป temp dir (กันเขียนทับไฟล์จริงตอนเทส)
settings.SEED_CREDENTIALS_FILE = os.path.join(
    tempfile.mkdtemp(prefix="pixel_seed_test_"), "seed_credentials.txt"
)

_TABLES = ("users",)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_db_url():
    db_name = f"test_db_{uuid.uuid4().hex}"
    parsed = urlparse(settings.DATABASE_URL)
    base = f"{parsed.scheme}://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port}"
    sys_url = f"{base}/postgres"

    sys_conn = await asyncpg.connect(sys_url)
    try:
        await sys_conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await sys_conn.close()

    new_db_url = f"{base}/{db_name}"
    original = settings.DATABASE_URL
    settings.DATABASE_URL = new_db_url
    try:
        temp_pool = await asyncpg.create_pool(new_db_url)
        try:
            await init_db(temp_pool)
            existing = {
                r["tablename"]
                for r in await temp_pool.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            }
            missing = [t for t in _TABLES if t not in existing]
            assert not missing, f"init_db สร้าง schema ไม่ครบ — ขาดตาราง: {', '.join(missing)}"
        finally:
            await temp_pool.close()
    finally:
        settings.DATABASE_URL = original

    yield new_db_url

    sys_conn = await asyncpg.connect(sys_url)
    try:
        await sys_conn.execute(
            f"SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity"
            f" WHERE pg_stat_activity.datname = '{db_name}' AND pid <> pg_backend_pid()"
        )
        await sys_conn.execute(f'DROP DATABASE "{db_name}"')
    finally:
        await sys_conn.close()


@pytest_asyncio.fixture(scope="function")
async def db_pool(test_db_url):
    pool = await asyncpg.create_pool(test_db_url)
    yield pool
    await pool.close()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def clean_database(db_pool):
    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE users CASCADE")
    yield


@pytest.fixture(scope="function")
def client(test_db_url):
    original = settings.DATABASE_URL
    settings.DATABASE_URL = test_db_url
    with TestClient(app) as c:
        yield c
    settings.DATABASE_URL = original
