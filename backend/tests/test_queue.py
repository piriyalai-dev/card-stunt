"""Live queue (คิวแสดง) — CRUD + RBAC + advance เดินตามคิว."""
import pytest

AUTH = lambda token: {"Authorization": f"Bearer {token}"}  # noqa: E731


async def _stunts(client, admin, event_row, codes):
    ids = []
    for code in codes:
        r = client.post(f"/api/v1/events/{event_row['id']}/stunts",
                        json={"code": code, "title": code},
                        headers=AUTH(admin["token"]))
        assert r.status_code == 200, r.text
        ids.append(r.json()["id"])
    return ids


@pytest.mark.asyncio
async def test_queue_seeded_on_publish(client, admin, event_row, stand_row):
    ids = await _stunts(client, admin, event_row, ["S0", "S1", "S2"])
    assert client.post(f"/api/v1/events/{event_row['id']}/publish",
                       headers=AUTH(admin["token"])).status_code == 200
    q = client.get(f"/api/v1/events/{event_row['id']}/queue", headers=AUTH(admin["token"])).json()
    assert [i["stunt_id"] for i in q] == ids


@pytest.mark.asyncio
async def test_set_queue_reorder(client, admin, event_row, stand_row):
    ids = await _stunts(client, admin, event_row, ["S0", "S1", "S2"])
    r = client.put(f"/api/v1/events/{event_row['id']}/queue",
                   json={"order": [ids[2], ids[0], ids[1]]},
                   headers=AUTH(admin["token"]))
    assert r.status_code == 200, r.text
    assert [i["stunt_id"] for i in r.json()] == [ids[2], ids[0], ids[1]]


@pytest.mark.asyncio
async def test_set_queue_subset(client, admin, event_row, stand_row):
    """คิวเป็น subset ของฉากได้ (เลือกเฉพาะที่จะแสดงจริง)."""
    ids = await _stunts(client, admin, event_row, ["S0", "S1", "S2"])
    r = client.put(f"/api/v1/events/{event_row['id']}/queue",
                   json={"order": [ids[2], ids[0]]},
                   headers=AUTH(admin["token"]))
    assert r.status_code == 200, r.text
    assert [i["stunt_id"] for i in r.json()] == [ids[2], ids[0]]


@pytest.mark.asyncio
async def test_queue_insert_and_remove(client, admin, event_row, stand_row):
    ids = await _stunts(client, admin, event_row, ["S0", "S1", "S2"])
    assert client.put(f"/api/v1/events/{event_row['id']}/queue",
                      json={"order": [ids[0], ids[2]]},
                      headers=AUTH(admin["token"])).status_code == 200
    r = client.post(f"/api/v1/events/{event_row['id']}/queue/insert",
                    json={"stunt_id": ids[1], "position": 1},
                    headers=AUTH(admin["token"]))
    assert r.status_code == 200, r.text
    assert [i["stunt_id"] for i in r.json()] == [ids[0], ids[1], ids[2]]
    r = client.delete(f"/api/v1/events/{event_row['id']}/queue/{ids[1]}",
                      headers=AUTH(admin["token"]))
    assert [i["stunt_id"] for i in r.json()] == [ids[0], ids[2]]


@pytest.mark.asyncio
async def test_queue_rbac(client, admin, designer, staff, event_row, stand_row):
    ids = await _stunts(client, admin, event_row, ["S0", "S1"])
    # staff (CONTROL_LIVE) ทำได้
    assert client.put(f"/api/v1/events/{event_row['id']}/queue",
                      json={"order": ids}, headers=AUTH(staff["token"])).status_code == 200
    # designer (ไม่มี CONTROL_LIVE) ทำไม่ได้
    assert client.put(f"/api/v1/events/{event_row['id']}/queue",
                      json={"order": ids}, headers=AUTH(designer["token"])).status_code == 403


@pytest.mark.asyncio
async def test_advance_follows_queue_order(client, admin, event_row, stand_row):
    ids = await _stunts(client, admin, event_row, ["S0", "S1", "S2"])
    # กลับลำดับในคิว (ไม่ตรง order_index)
    assert client.put(f"/api/v1/events/{event_row['id']}/queue",
                      json={"order": [ids[2], ids[0], ids[1]]},
                      headers=AUTH(admin["token"])).status_code == 200
    assert client.post(f"/api/v1/events/{event_row['id']}/publish",
                       headers=AUTH(admin["token"])).status_code == 200
    state = client.get(f"/api/v1/events/{event_row['id']}/live",
                       headers=AUTH(admin["token"])).json()
    assert state["current_stunt_id"] == ids[2]
    r = client.post(f"/api/v1/events/{event_row['id']}/live/advance", json={"action": "next"},
                    headers=AUTH(admin["token"]))
    assert r.json()["current_stunt_id"] == ids[0]
