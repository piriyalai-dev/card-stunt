"""
Fixtures สำหรับ pytest integration tests ของ Pixel Stand.

Pattern ตาม prsc_portal:
- test_db_url: สร้าง DB ใหม่แบบสุ่มชื่อทุก session → init_db → drop ตอนจบ
- client: เปลี่ยน settings.DATABASE_URL ไปยัง test DB
- clean_database: TRUNCATE ทุกตารางก่อนทุก test
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
from services.auth_service import hash_password

# ไฟล์ credentials ของ seed users — ชี้ไป temp dir (กันเขียนทับไฟล์จริงตอนเทส)
settings.SEED_CREDENTIALS_FILE = os.path.join(
    tempfile.mkdtemp(prefix="pixel_seed_test_"), "seed_credentials.txt"
)
# media ลง temp dir — กันเขียนลง /data/media ของ container
settings.MEDIA_STORAGE_DIR = tempfile.mkdtemp(prefix="pixel_media_test_")

_TABLES = (
    "users", "events", "stands", "palettes", "palette_colors", "stunts",
    "stunt_revisions", "seat_rosters", "export_jobs", "audit_logs",
)


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
        await conn.execute(f"TRUNCATE TABLE {', '.join(_TABLES)} RESTART IDENTITY CASCADE")
    try:
        from core import cache
        await cache.flush_test_db()
    except Exception:
        pass
    yield


@pytest.fixture(scope="function")
def client(test_db_url):
    original = settings.DATABASE_URL
    settings.DATABASE_URL = test_db_url
    with TestClient(app) as c:
        yield c
    settings.DATABASE_URL = original


# ── factories / helpers ────────────────────────────────────────────

async def _create_user(pool, username, password="secret123", role="admin", display_name="T"):
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO users (username, password_hash, display_name, role) VALUES ($1,$2,$3,$4) RETURNING id",
            username, hash_password(password), display_name, role,
        )


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _login(client, username, password="secret123"):
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest_asyncio.fixture
async def admin(db_pool, client):
    uid = await _create_user(db_pool, "admin", "secret123", "admin", "Admin")
    token = await _login(client, "admin")
    return {"id": uid, "username": "admin", "token": token}


@pytest_asyncio.fixture
async def designer(db_pool, client):
    uid = await _create_user(db_pool, "designer", "secret123", "designer", "Designer")
    token = await _login(client, "designer")
    return {"id": uid, "username": "designer", "token": token}


@pytest_asyncio.fixture
async def staff(db_pool, client):
    uid = await _create_user(db_pool, "staff", "secret123", "staff", "Staff")
    token = await _login(client, "staff")
    return {"id": uid, "username": "staff", "token": token}


@pytest_asyncio.fixture
async def event_row(admin, client):
    res = client.post("/api/v1/events", json={"name": "กีฬาสี 69", "slug": "sport69"},
                      headers=_auth(admin["token"]))
    assert res.status_code == 200, res.text
    return res.json()


@pytest_asyncio.fixture
async def stand_row(admin, client, event_row):
    res = client.post(f"/api/v1/events/{event_row['id']}/stands",
                      json={"name": "โซนกลาง", "rows": 9, "cols": 33},
                      headers=_auth(admin["token"]))
    assert res.status_code == 200, res.text
    return res.json()


@pytest_asyncio.fixture
async def palette_row(admin, client, event_row):
    res = client.post(f"/api/v1/events/{event_row['id']}/palettes",
                      json={"name": "ชุดสี 1", "colors": [
                          {"code": "01", "name_th": "แดงสด", "hex": "#B91C1C"},
                          {"code": "02", "name_th": "เขียว", "hex": "#15803D"},
                      ]},
                      headers=_auth(admin["token"]))
    assert res.status_code == 200, res.text
    return res.json()
