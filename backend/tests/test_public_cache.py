"""Public endpoints + ETag/304."""
import pytest


async def _published(client, admin, event_row, stand_row, palette_row):
    color_a = palette_row["colors"][0]["id"]
    s = client.post(f"/api/v1/events/{event_row['id']}/stunts",
                    json={"code": "S1", "title": "ฉาก", "palette_a_id": palette_row["id"]},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    sid = s.json()["id"]
    grid = [color_a] * (165 * 45)
    assert client.put(f"/api/v1/stunts/{sid}/grid", json={"grid_data_a": grid},
                      headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 200
    assert client.post(f"/api/v1/events/{event_row['id']}/publish",
                       headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 200


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
    assert len(body["stunts"]) == 1
    assert "ETag" in r.headers


@pytest.mark.asyncio
async def test_etag_304(client, admin, event_row, stand_row, palette_row):
    await _published(client, admin, event_row, stand_row, palette_row)
    r1 = client.get("/api/v1/public/events/sport69/meta")
    etag = r1.headers["ETag"]
    r2 = client.get("/api/v1/public/events/sport69/meta", headers={"If-None-Match": etag})
    assert r2.status_code == 304


@pytest.mark.asyncio
async def test_seat_returns_plate(client, admin, event_row, stand_row, palette_row):
    await _published(client, admin, event_row, stand_row, palette_row)
    r = client.get("/api/v1/public/events/sport69/seat", params={"row": 1, "col": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["row_label"] == "A"
    assert body["seat_label"] == "1"
    # plate 5×5 = 25 cells ต่อด้าน
    assert len(body["stunts"][0]["side_a"]) == 5
    assert len(body["stunts"][0]["side_a"][0]) == 5


@pytest.mark.asyncio
async def test_version(client, admin, event_row, stand_row, palette_row):
    await _published(client, admin, event_row, stand_row, palette_row)
    r = client.get("/api/v1/public/events/sport69/version")
    assert r.status_code == 200
    assert r.json()["published_version"] > 0
