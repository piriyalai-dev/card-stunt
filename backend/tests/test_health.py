import pytest


@pytest.mark.asyncio
async def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["database"] == "connected"


class _DownPool:
    """pool ปลอมที่ล้มเหลวตอน acquire — จำลอง DB ล่ม."""

    def acquire(self):
        raise RuntimeError("db down")


@pytest.mark.asyncio
async def test_health_db_down_returns_503(client):
    from main import app

    real = app.state.db_pool
    app.state.db_pool = _DownPool()
    try:
        res = client.get("/health")
        assert res.status_code == 503
        assert res.json()["status"] == "error"
    finally:
        app.state.db_pool = real


@pytest.mark.asyncio
async def test_body_size_limit_returns_413(client):
    from core.config import settings

    original = settings.MAX_REQUEST_BODY_MB
    settings.MAX_REQUEST_BODY_MB = 0  # reject ทุก body ที่ไม่ว่าง
    try:
        res = client.post("/api/v1/auth/login", json={"username": "a", "password": "b"})
        assert res.status_code == 413
    finally:
        settings.MAX_REQUEST_BODY_MB = original
