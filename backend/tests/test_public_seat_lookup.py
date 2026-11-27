"""Phase 5 — public seat lookup by student_code + privacy gate."""
import pytest

AUTH = lambda token: {"Authorization": f"Bearer {token}"}  # noqa: E731


def _publish(client, admin, event_row, stand_row, palette_row, *, enable_lookup=True):
    headers = AUTH(admin["token"])
    color = palette_row["colors"][0]["id"]
    stunt = client.post(
        f"/api/v1/events/{event_row['id']}/stunts",
        json={"code": "S1", "title": "ฉาก", "stand_id": stand_row["id"],
              "palette_a_id": palette_row["id"]},
        headers=headers,
    ).json()
    cells = stand_row["rows"] * stand_row["sub_rows"] * stand_row["cols"] * stand_row["sub_cols"]
    assert client.put(
        f"/api/v1/stunts/{stunt['id']}/grid",
        json={"grid_data_a": [color] * cells}, headers=headers,
    ).status_code == 200
    assert client.post(
        f"/api/v1/events/{event_row['id']}/rosters",
        json={"stand_id": stand_row["id"], "row_index": 0, "col_index": 1,
              "student_name": "นางสาว ข", "student_code": "Ab12"},
        headers=headers,
    ).status_code == 200
    if enable_lookup:
        assert client.patch(
            f"/api/v1/events/{event_row['id']}",
            json={"roster_lookup_enabled": True}, headers=headers,
        ).status_code == 200
    assert client.post(
        f"/api/v1/events/{event_row['id']}/publish", headers=headers,
    ).status_code == 200


@pytest.mark.asyncio
async def test_lookup_by_student_code_case_insensitive(client, admin, event_row, stand_row, palette_row):
    _publish(client, admin, event_row, stand_row, palette_row)
    r = client.get("/api/v1/public/events/sport69/seat", params={"student_code": "ab12"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["seat_label"] == "2"
    assert body["row_label"] == "A"
    assert body["student"] == {"student_code": "Ab12", "student_name": "นางสาว ข"}
    assert len(body["stunts"][0]["side_a"]) == 5


@pytest.mark.asyncio
async def test_lookup_disabled_is_404(client, admin, event_row, stand_row, palette_row):
    _publish(client, admin, event_row, stand_row, palette_row, enable_lookup=False)
    r = client.get("/api/v1/public/events/sport69/seat", params={"student_code": "Ab12"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_unknown_student_code_is_404(client, admin, event_row, stand_row, palette_row):
    _publish(client, admin, event_row, stand_row, palette_row)
    r = client.get("/api/v1/public/events/sport69/seat", params={"student_code": "99999"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_row_col_hides_student_when_lookup_disabled(client, admin, event_row, stand_row, palette_row):
    _publish(client, admin, event_row, stand_row, palette_row, enable_lookup=False)
    r = client.get("/api/v1/public/events/sport69/seat", params={"row": 1, "col": 2})
    assert r.status_code == 200, r.text
    assert r.json()["student"] is None


@pytest.mark.asyncio
async def test_seat_only_returns_stunts_of_its_stand(client, admin, event_row, stand_row, palette_row):
    headers = AUTH(admin["token"])
    color = palette_row["colors"][0]["id"]
    stand2 = client.post(
        f"/api/v1/events/{event_row['id']}/stands",
        json={"name": "โซนหลัง", "rows": 2, "cols": 2}, headers=headers,
    ).json()

    for stand, code in ((stand_row, "S1"), (stand2, "S2")):
        stunt = client.post(
            f"/api/v1/events/{event_row['id']}/stunts",
            json={"code": code, "title": code, "stand_id": stand["id"],
                  "palette_a_id": palette_row["id"]},
            headers=headers,
        ).json()
        cells = stand["grid_width"] * stand["grid_height"]
        assert client.put(
            f"/api/v1/stunts/{stunt['id']}/grid",
            json={"grid_data_a": [color] * cells}, headers=headers,
        ).status_code == 200

    assert client.post(
        f"/api/v1/events/{event_row['id']}/publish", headers=headers,
    ).status_code == 200

    s1 = client.get("/api/v1/public/events/sport69/seat",
                    params={"row": 1, "col": 1, "stand_id": stand_row["id"]}).json()
    s2 = client.get("/api/v1/public/events/sport69/seat",
                    params={"row": 1, "col": 1, "stand_id": stand2["id"]}).json()
    assert [s["code"] for s in s1["stunts"]] == ["S1"]
    assert [s["code"] for s in s2["stunts"]] == ["S2"]


@pytest.mark.asyncio
async def test_missing_seat_params_is_400(client, admin, event_row, stand_row, palette_row):
    _publish(client, admin, event_row, stand_row, palette_row)
    r = client.get("/api/v1/public/events/sport69/seat")
    assert r.status_code == 400
