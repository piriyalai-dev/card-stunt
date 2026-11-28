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
    res = client.post("/api/v1/auth/login", json={"username": "admin_test", "password": "secret123"})
    assert res.status_code == 200
    data = res.json()
    assert data["access_token"]
    assert data["user"]["role"] == "admin"
    assert data["user"]["is_admin"] is True
    assert "MANAGE_USERS" in data["user"]["permissions"]


# === Failures ===
@pytest.mark.asyncio
async def test_login_wrong_password(client, admin_user):
    res = client.post("/api/v1/auth/login", json={"username": "admin_test", "password": "wrongpass"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user(client):
    res = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "whatever"})
    assert res.status_code == 401


# === /me ===
@pytest.mark.asyncio
async def test_me_requires_auth(client):
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me_with_token(client, admin_user):
    login = client.post("/api/v1/auth/login", json={"username": "admin_test", "password": "secret123"})
    token = login.json()["access_token"]
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["username"] == "admin_test"


# === change-password ===
@pytest.mark.asyncio
async def test_change_password(client, admin_user):
    login = client.post("/api/v1/auth/login", json={"username": "admin_test", "password": "secret123"})
    token = login.json()["access_token"]
    res = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "secret123", "new_password": "newpass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    # รหัสเก่าใช้ไม่ได้
    assert client.post("/api/v1/auth/login", json={"username": "admin_test", "password": "secret123"}).status_code == 401
    # รหัสใหม่ใช้ได้
    assert client.post("/api/v1/auth/login", json={"username": "admin_test", "password": "newpass456"}).status_code == 200


# === deleted user / must_change_password (Wave 1 hardening) ===
@pytest.mark.asyncio
async def test_deleted_user_token_rejected(client, db_pool, admin_user):
    token = client.post("/api/v1/auth/login",
                        json={"username": "admin_test", "password": "secret123"}).json()["access_token"]
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET deleted_at = NOW() WHERE username = 'admin_test'")
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_must_change_password_gate(client, db_pool):
    async with db_pool.acquire() as conn:
        await conn.fetchval(
            "INSERT INTO users (username, password_hash, display_name, role, must_change_password)"
            " VALUES ($1,$2,$3,$4, TRUE) RETURNING id",
            "forced_change", auth_service.hash_password("secret123"), "Forced", "admin",
        )
    token = client.post("/api/v1/auth/login",
                        json={"username": "forced_change", "password": "secret123"}).json()["access_token"]

    # บล็อก endpoint อื่นด้วย 403
    assert client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"}).status_code == 403
    # /auth/me ยังใช้ได้ (เพื่อให้ frontend รู้ว่าเป็นใคร)
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    # /auth/change-password ยังใช้ได้ และเคลียร์ must_change_password
    res = client.post("/api/v1/auth/change-password",
                      json={"old_password": "secret123", "new_password": "newpass789"},
                      headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    # หลังเปลี่ยนรหัส ใช้ endpoint อื่นได้แล้ว (gate อ่าน flag จาก DB ทุก request)
    assert client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"}).status_code == 200


# === password policy ===
@pytest.mark.asyncio
async def test_change_password_rejects_weak(client, admin_user):
    token = client.post("/api/v1/auth/login",
                        json={"username": "admin_test", "password": "secret123"}).json()["access_token"]
    # สั้นเกินไป
    assert client.post("/api/v1/auth/change-password",
                       json={"old_password": "secret123", "new_password": "short"},
                       headers={"Authorization": f"Bearer {token}"}).status_code == 422
    # ไม่มีตัวเลข
    assert client.post("/api/v1/auth/change-password",
                       json={"old_password": "secret123", "new_password": "allletters"},
                       headers={"Authorization": f"Bearer {token}"}).status_code == 422


@pytest.mark.asyncio
async def test_create_user_rejects_weak_password(client, admin):
    res = client.post("/api/v1/users",
                      json={"username": "weakuser", "password": "abc", "role": "staff"},
                      headers={"Authorization": f"Bearer {admin['token']}"})
    assert res.status_code == 422


# === ไม่ leak ว่า user มีจริงไหม (enumeration) ===
@pytest.mark.asyncio
async def test_login_does_not_leak_user_existence(client, admin_user):
    unknown = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "whatever"})
    wrong_pw = client.post("/api/v1/auth/login", json={"username": "admin_test", "password": "wrongpass"})
    assert unknown.status_code == wrong_pw.status_code == 401
    assert unknown.json()["detail"] == wrong_pw.json()["detail"]


# === rate limit login ===
@pytest.mark.asyncio
async def test_login_rate_limited(client, admin_user):
    from core.config import settings

    payload = {"username": "admin_test", "password": "wrongpass"}
    statuses = [
        client.post("/api/v1/auth/login", json=payload).status_code
        for _ in range(settings.LOGIN_RATE_LIMIT_MAX + 1)
    ]
    assert statuses[-2] == 401  # ยังไม่ถึงเพดาน
    assert statuses[-1] == 429  # เกินเพดาน


@pytest.mark.asyncio
async def test_check_rate_limit_generic():
    from core import ratelimit
    from core.exceptions import RateLimitError

    ratelimit.reset()
    try:
        for _ in range(3):
            await ratelimit.check_rate_limit(["test:rl"], 3, 60)
        with pytest.raises(RateLimitError):
            await ratelimit.check_rate_limit(["test:rl"], 3, 60)
    finally:
        ratelimit.reset()


# === audit change-password ===
@pytest.mark.asyncio
async def test_change_password_is_audited(client, db_pool, admin_user):
    token = client.post("/api/v1/auth/login",
                        json={"username": "admin_test", "password": "secret123"}).json()["access_token"]
    res = client.post("/api/v1/auth/change-password",
                      json={"old_password": "secret123", "new_password": "newpass456"},
                      headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM audit_logs WHERE action = 'CHANGE_PASSWORD'")
    assert row is not None


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
