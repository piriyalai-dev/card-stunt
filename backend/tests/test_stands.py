"""Stand config + blocked seats + resize."""
import pytest


@pytest.mark.asyncio
async def test_stand_grid_dims(client, admin, event_row, stand_row):
    assert stand_row["grid_width"] == 165
    assert stand_row["grid_height"] == 45


@pytest.mark.asyncio
async def test_blocked_seats_validation(client, admin, stand_row):
    # in bounds ok
    r = client.patch(f"/api/v1/stands/{stand_row['id']}/blocked-seats",
                     json={"blocked_seats": [{"row": 0, "col": 0}]},
                     headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text
    # out of bounds → 400
    r = client.patch(f"/api/v1/stands/{stand_row['id']}/blocked-seats",
                     json={"blocked_seats": [{"row": 99, "col": 0}]},
                     headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_resize_without_grid(client, admin, stand_row):
    r = client.post(f"/api/v1/stands/{stand_row['id']}/resize",
                    json={"rows": 10, "cols": 33},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text
    assert r.json()["rows"] == 10
    assert r.json()["grid_height"] == 50
