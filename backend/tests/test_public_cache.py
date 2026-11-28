"""Public endpoints + ETag/304."""
import pytest


async def _published(client, admin, event_row, stand_row, palette_row):
    headers = {"Authorization": f"Bearer {admin['token']}"}
    color_a = palette_row["colors"][0]["id"]
    assert client.patch(
        f"/api/v1/events/{event_row['id']}",
        json={"palette_a_id": palette_row["id"], "palette_b_id": palette_row["id"]},
        headers=headers,
    ).status_code == 200
    s = client.post(f"/api/v1/events/{event_row['id']}/stunts",
                    json={"code": "S1", "title": "ฉาก", "side": "A"},
                    headers=headers)
    sid = s.json()["id"]
    grid = [color_a] * (165 * 45)
    assert client.put(f"/api/v1/stunts/{sid}/grid", json={"grid_data": grid},
                      headers=headers).status_code == 200
    roster = client.post(f"/api/v1/events/{event_row['id']}/rosters",
                         json={"stand_id": stand_row["id"], "row_index": 0, "col_index": 0,
                               "student_name": "นาย ก"},
                         headers=headers)
    assert roster.status_code == 200, roster.text
    assert client.post(f"/api/v1/events/{event_row['id']}/publish",
                       headers=headers).status_code == 200
    return roster.json()["access_code"]


@pytest.mark.asyncio
async def test_meta_404_before_publish(client, admin, event_row):
    assert client.get("/api/v1/public/events/sport69/meta").status_code == 404


@pytest.mark.asyncio
async def test_meta_after_publish(client, admin, event_row, stand_row, palette_row):
    await _published(client, admin, event_row, stand_row, palette_row)
    r = client.get("/api/v1/public/events/sport69/meta")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "sport69"
    # meta หดแล้ว — ไม่พก stunts/palettes/stands (ล็อกดาวน์)
    assert "stunts" not in body
    assert "palettes" not in body
    assert body["live"]["total"] == 1
    assert "ETag" in r.headers


@pytest.mark.asyncio
async def test_etag_304(client, admin, event_row, stand_row, palette_row):
    await _published(client, admin, event_row, stand_row, palette_row)
    r1 = client.get("/api/v1/public/events/sport69/meta")
    etag = r1.headers["ETag"]
    r2 = client.get("/api/v1/public/events/sport69/meta", headers={"If-None-Match": etag})
    assert r2.status_code == 304


@pytest.mark.asyncio
async def test_claim_returns_plate(client, admin, event_row, stand_row, palette_row):
    code = await _published(client, admin, event_row, stand_row, palette_row)
    r = client.post("/api/v1/public/events/sport69/claim", json={"access_code": code})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["row_label"] == "A"
    assert body["seat_label"] == "1"
    # plate 5×5 = 25 cells
    assert len(body["stunts"][0]["plate"]) == 5
    assert len(body["stunts"][0]["plate"][0]) == 5


@pytest.mark.asyncio
async def test_version(client, admin, event_row, stand_row, palette_row):
    await _published(client, admin, event_row, stand_row, palette_row)
    r = client.get("/api/v1/public/events/sport69/version")
    assert r.status_code == 200
    assert r.json()["published_version"] > 0
