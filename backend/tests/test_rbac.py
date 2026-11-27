"""RBAC matrix — admin ⊃ designer ⊃ staff (หัวใจ Phase 3)."""
import pytest


@pytest.mark.asyncio
async def test_rbac_matrix(client, admin, designer, staff, event_row, stand_row, palette_row):
    # admin ทำได้ทุกอย่าง
    assert client.post("/api/v1/events", json={"name": "e2", "slug": "e2"},
                       headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 200
    # designer: จัด palette/stunt ได้ แต่ event/stand ไม่ได้
    assert client.post("/api/v1/events", json={"name": "x", "slug": "x"},
                       headers={"Authorization": f"Bearer {designer['token']}"}).status_code == 403
    assert client.post(f"/api/v1/events/{event_row['id']}/stands",
                       json={"name": "s2", "rows": 9, "cols": 33},
                       headers={"Authorization": f"Bearer {designer['token']}"}).status_code == 403
    assert client.post(f"/api/v1/events/{event_row['id']}/palettes",
                       json={"name": "p2"},
                       headers={"Authorization": f"Bearer {designer['token']}"}).status_code == 200
    # staff: roster/export/live ได้ แต่ stunt ไม่ได้
    assert client.post(f"/api/v1/events/{event_row['id']}/stunts",
                       json={"code": "S1", "title": "ฉาก 1"},
                       headers={"Authorization": f"Bearer {staff['token']}"}).status_code == 403
    assert client.post(f"/api/v1/events/{event_row['id']}/exports",
                       json={"format": "pdf"},
                       headers={"Authorization": f"Bearer {staff['token']}"}).status_code == 200


@pytest.mark.asyncio
async def test_users_admin_only(client, admin, designer):
    assert client.get("/api/v1/users",
                      headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 200
    assert client.get("/api/v1/users",
                      headers={"Authorization": f"Bearer {designer['token']}"}).status_code == 403


@pytest.mark.asyncio
async def test_audit_admin_only(client, admin, staff):
    assert client.get("/api/v1/audit-logs",
                      headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 200
    assert client.get("/api/v1/audit-logs",
                      headers={"Authorization": f"Bearer {staff['token']}"}).status_code == 403


@pytest.mark.asyncio
async def test_public_no_auth(client, admin, event_row, stand_row, palette_row):
    # publish ก่อน
    assert client.post(f"/api/v1/events/{event_row['id']}/stunts",
                       json={"code": "S1", "title": "ฉาก 1"},
                       headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 200
    assert client.post(f"/api/v1/events/{event_row['id']}/publish",
                       headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 200
    # public ไม่ต้อง auth
    assert client.get("/api/v1/public/events/sport69/meta").status_code == 200
