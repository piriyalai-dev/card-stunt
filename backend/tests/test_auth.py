# === Auth Flow Tests ===
import pytest
import pytest_asyncio

from core.exceptions import ForbiddenError
from core.rbac import require_permission
from services import auth_service


async def _create_user(pool, username, password, role="admin", display_name="Test User"):
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO users (username, password_hash, display_name, role) VALUES ($1, $2, $3, $4) RETURNING id",
            username, auth_service.hash_password(password), display_name, role,
        )


@pytest_asyncio.fixture
async def admin_user(db_pool):
    uid = await _create_user(db_pool, "admin_test", "secret123", "admin", "Test Admin")
    return {"id": uid, "username": "admin_test", "password": "secret123"}


# === Login happy path ===
@pytest.mark.asyncio
async def test_login_success(client, admin_user):
    res = client.post("/api/auth/login", json={"username": "admin_test", "password": "secret123"})
    assert res.status_code == 200
    data = res.json()
    assert data["access_token"]
    assert data["user"]["role"] == "admin"
    assert data["user"]["is_admin"] is True
    assert "MANAGE_USERS" in data["user"]["permissions"]


# === Failures ===
@pytest.mark.asyncio
async def test_login_wrong_password(client, admin_user):
    res = client.post("/api/auth/login", json={"username": "admin_test", "password": "wrongpass"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user(client):
    res = client.post("/api/auth/login", json={"username": "nobody", "password": "whatever"})
    assert res.status_code == 401


# === /me ===
@pytest.mark.asyncio
async def test_me_requires_auth(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me_with_token(client, admin_user):
    login = client.post("/api/auth/login", json={"username": "admin_test", "password": "secret123"})
    token = login.json()["access_token"]
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["username"] == "admin_test"


# === change-password ===
@pytest.mark.asyncio
async def test_change_password(client, admin_user):
    login = client.post("/api/auth/login", json={"username": "admin_test", "password": "secret123"})
    token = login.json()["access_token"]
    res = client.post(
        "/api/auth/change-password",
        json={"old_password": "secret123", "new_password": "newpass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    # รหัสเก่าใช้ไม่ได้
    assert client.post("/api/auth/login", json={"username": "admin_test", "password": "secret123"}).status_code == 401
    # รหัสใหม่ใช้ได้
    assert client.post("/api/auth/login", json={"username": "admin_test", "password": "newpass456"}).status_code == 200


# === RBAC ===
@pytest.mark.asyncio
async def test_rbac_require_permission(db_pool):
    admin_id = await _create_user(db_pool, "rbac_admin", "pw", "admin", "Admin")
    staff_id = await _create_user(db_pool, "rbac_staff", "pw", "staff", "Staff")
    async with db_pool.acquire() as conn:
        # admin ผ่านทุก permission (is_admin)
        await require_permission(conn, admin_id, "MANAGE_USERS")
        # staff ไม่มี MANAGE_USERS
        with pytest.raises(ForbiddenError):
            await require_permission(conn, staff_id, "MANAGE_USERS")
        # staff มี CONTROL_LIVE
        await require_permission(conn, staff_id, "CONTROL_LIVE")
