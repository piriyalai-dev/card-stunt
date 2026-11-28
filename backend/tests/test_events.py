"""Event CRUD + duplicate + publish + slug."""
import pytest


@pytest.mark.asyncio
async def test_create_and_get(client, admin):
    r = client.post("/api/v1/events", json={"name": "วันวิชาการ", "slug": "academic"},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200
    ev = r.json()
    assert ev["slug"] == "academic"
    assert client.get(f"/api/v1/events/{ev['id']}",
                      headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 200


@pytest.mark.asyncio
async def test_slug_conflict(client, admin):
    client.post("/api/v1/events", json={"name": "A", "slug": "dup"},
                headers={"Authorization": f"Bearer {admin['token']}"})
    r = client.post("/api/v1/events", json={"name": "B", "slug": "dup"},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_duplicate_copies_subtree(client, admin, event_row, stand_row, palette_row):
    r = client.post(f"/api/v1/events/{event_row['id']}/duplicate",
                    json={"name": "กีฬาสี 70", "slug": "sport70"},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text
    new_id = r.json()["id"]
    assert len(client.get(f"/api/v1/events/{new_id}/stands",
                          headers={"Authorization": f"Bearer {admin['token']}"}).json()) == 1
    assert len(client.get(f"/api/v1/events/{new_id}/palettes",
                          headers={"Authorization": f"Bearer {admin['token']}"}).json()) == 1


@pytest.mark.asyncio
async def test_duplicate_copies_rosters_and_queue_with_new_codes(client, admin, event_row, stand_row):
    headers = {"Authorization": f"Bearer {admin['token']}"}
    assert client.post(f"/api/v1/events/{event_row['id']}/stunts",
                       json={"code": "S1", "title": "ฉาก", "side": "A"}, headers=headers).status_code == 200
    r = client.post(f"/api/v1/events/{event_row['id']}/rosters",
                    json={"stand_id": stand_row["id"], "row_index": 0, "col_index": 0, "student_name": "ก"},
                    headers=headers)
    assert r.status_code == 200, r.text
    src_code = r.json()["access_code"]
    # publish source → seed queue
    assert client.post(f"/api/v1/events/{event_row['id']}/publish", headers=headers).status_code == 200

    dup = client.post(f"/api/v1/events/{event_row['id']}/duplicate",
                      json={"name": "กีฬาสี 70", "slug": "sport70"}, headers=headers)
    assert dup.status_code == 200, dup.text
    new_id = dup.json()["id"]

    new_rosters = client.get(f"/api/v1/events/{new_id}/rosters", headers=headers).json()
    assert len(new_rosters) == 1
    assert new_rosters[0]["access_code"] != src_code  # mint ใหม่ ไม่ copy code ข้ามงาน

    new_queue = client.get(f"/api/v1/events/{new_id}/queue", headers=headers).json()
    assert len(new_queue) == 1  # queue remap stunt_id


@pytest.mark.asyncio
async def test_publish_requires_stunt(client, admin, event_row, stand_row):
    r = client.post(f"/api/v1/events/{event_row['id']}/publish",
                    headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_soft_delete_hides_event(client, admin, event_row):
    assert client.delete(f"/api/v1/events/{event_row['id']}",
                         headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 200
    assert client.get(f"/api/v1/events/{event_row['id']}",
                      headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 404
