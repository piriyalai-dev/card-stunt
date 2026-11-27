"""Audit log: mutation writes 1 row in same tx + login audit + keyset."""
import pytest


@pytest.mark.asyncio
async def test_mutation_writes_audit(client, admin, db_pool):
    client.post("/api/v1/events", json={"name": "audit-test", "slug": "audit-test"},
                headers={"Authorization": f"Bearer {admin['token']}"})
    async with db_pool.acquire() as conn:
        n = await conn.fetchval("SELECT COUNT(*) FROM audit_logs WHERE action = 'CREATE_EVENT'")
    assert n == 1


@pytest.mark.asyncio
async def test_login_audit_success(client, admin, db_pool):
    client.post("/api/v1/auth/login", json={"username": "admin", "password": "secret123"})
    async with db_pool.acquire() as conn:
        n = await conn.fetchval("SELECT COUNT(*) FROM audit_logs WHERE service_name = 'auth' AND action = 'LOGIN'")
    assert n >= 1


@pytest.mark.asyncio
async def test_login_audit_failure(client, admin, db_pool):
    client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrongpass"})
    async with db_pool.acquire() as conn:
        n = await conn.fetchval("SELECT COUNT(*) FROM audit_logs WHERE action = 'LOGIN_FAILED'")
    assert n >= 1


@pytest.mark.asyncio
async def test_audit_keyset_list(client, admin):
    for i in range(5):
        client.post("/api/v1/events", json={"name": f"e{i}", "slug": f"e{i}"},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    r = client.get("/api/v1/audit-logs", params={"limit": 2},
                   headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    assert body["has_more"] is True
    assert body["next_cursor"] is not None
