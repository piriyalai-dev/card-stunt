"""Phase 5 — public access-code claim (ล็อกดาวน์ viewer: รหัสสุ่มแทนการเลือกที่นั่ง)."""
import pytest

AUTH = lambda token: {"Authorization": f"Bearer {token}"}  # noqa: E731


def _publish(client, admin, event_row, stand_row, palette_row):
    """สร้างฉาก + ที่นั่ง (มี access_code) + publish — คืน access_code ของที่นั่ง."""
    headers = AUTH(admin["token"])
    color = palette_row["colors"][0]["id"]
    assert client.patch(
        f"/api/v1/events/{event_row['id']}",
        json={"palette_a_id": palette_row["id"], "palette_b_id": palette_row["id"]},
        headers=headers,
    ).status_code == 200
    stunt = client.post(
        f"/api/v1/events/{event_row['id']}/stunts",
        json={"code": "S1", "title": "ฉาก", "stand_id": stand_row["id"], "side": "A"},
        headers=headers,
    ).json()
    cells = stand_row["rows"] * stand_row["sub_rows"] * stand_row["cols"] * stand_row["sub_cols"]
    assert client.put(
        f"/api/v1/stunts/{stunt['id']}/grid",
        json={"grid_data": [color] * cells}, headers=headers,
    ).status_code == 200
    roster = client.post(
        f"/api/v1/events/{event_row['id']}/rosters",
        json={"stand_id": stand_row["id"], "row_index": 0, "col_index": 1,
              "student_name": "นางสาว ข", "student_code": "Ab12"},
        headers=headers,
    )
    assert roster.status_code == 200, roster.text
    assert client.post(
        f"/api/v1/events/{event_row['id']}/publish", headers=headers,
    ).status_code == 200
    return roster.json()["access_code"]


@pytest.mark.asyncio
async def test_claim_by_access_code(client, admin, event_row, stand_row, palette_row):
    code = _publish(client, admin, event_row, stand_row, palette_row)
    r = client.post("/api/v1/public/events/sport69/claim", json={"access_code": code})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["seat_label"] == "2"
    assert body["row_label"] == "A"
    assert body["student"] == {"student_code": "Ab12", "student_name": "นางสาว ข"}
    # stunts: side + plate เดียว (5×5)
    assert body["stunts"][0]["side"] == "A"
    assert len(body["stunts"][0]["plate"]) == 5
    assert len(body["stunts"][0]["plate"][0]) == 5
    # palettes แนบมาด้วย (render plate ออฟไลน์ได้)
    assert len(body["palettes"]) == 1
    assert body["palettes"][0]["colors"][0]["id"] == palette_row["colors"][0]["id"]


@pytest.mark.asyncio
async def test_claim_case_insensitive(client, admin, event_row, stand_row, palette_row):
    code = _publish(client, admin, event_row, stand_row, palette_row)
    r = client.post("/api/v1/public/events/sport69/claim", json={"access_code": code.lower()})
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_claim_unknown_code_404(client, admin, event_row, stand_row, palette_row):
    _publish(client, admin, event_row, stand_row, palette_row)
    r = client.post("/api/v1/public/events/sport69/claim", json={"access_code": "ZZZZZZZZ"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_claim_empty_code_400(client, admin, event_row, stand_row, palette_row):
    _publish(client, admin, event_row, stand_row, palette_row)
    r = client.post("/api/v1/public/events/sport69/claim", json={"access_code": "   "})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_seat_only_returns_stunts_of_its_stand(client, admin, event_row, stand_row, palette_row):
    headers = AUTH(admin["token"])
    color = palette_row["colors"][0]["id"]
    assert client.patch(
        f"/api/v1/events/{event_row['id']}",
        json={"palette_a_id": palette_row["id"], "palette_b_id": palette_row["id"]},
        headers=headers,
    ).status_code == 200
    stand2 = client.post(
        f"/api/v1/events/{event_row['id']}/stands",
        json={"name": "โซนหลัง", "rows": 2, "cols": 2}, headers=headers,
    ).json()

    for stand, code in ((stand_row, "S1"), (stand2, "S2")):
        stunt = client.post(
            f"/api/v1/events/{event_row['id']}/stunts",
            json={"code": code, "title": code, "stand_id": stand["id"], "side": "A"},
            headers=headers,
        ).json()
        cells = stand["grid_width"] * stand["grid_height"]
        assert client.put(
            f"/api/v1/stunts/{stunt['id']}/grid",
            json={"grid_data": [color] * cells}, headers=headers,
        ).status_code == 200

    # roster 2 ที่นั่ง คนละ stand
    r1 = client.post(
        f"/api/v1/events/{event_row['id']}/rosters",
        json={"stand_id": stand_row["id"], "row_index": 0, "col_index": 0, "student_name": "ก"},
        headers=headers,
    ).json()
    r2 = client.post(
        f"/api/v1/events/{event_row['id']}/rosters",
        json={"stand_id": stand2["id"], "row_index": 0, "col_index": 0, "student_name": "ข"},
        headers=headers,
    ).json()
    assert client.post(
        f"/api/v1/events/{event_row['id']}/publish", headers=headers,
    ).status_code == 200

    s1 = client.post("/api/v1/public/events/sport69/claim",
                     json={"access_code": r1["access_code"]}).json()
    s2 = client.post("/api/v1/public/events/sport69/claim",
                     json={"access_code": r2["access_code"]}).json()
    assert [s["code"] for s in s1["stunts"]] == ["S1"]
    assert [s["code"] for s in s2["stunts"]] == ["S2"]
