"""Roster manual + CSV import + bounds/dupes."""
import pytest


@pytest.mark.asyncio
async def test_create_roster(client, admin, event_row, stand_row):
    r = client.post(f"/api/v1/events/{event_row['id']}/rosters",
                    json={"stand_id": stand_row["id"], "row_index": 0, "col_index": 0,
                          "student_name": "นาย ก", "student_code": "11111"},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text
    assert r.json()["row_label"] == "A"
    assert r.json()["seat_label"] == "1"


@pytest.mark.asyncio
async def test_roster_dup_seat(client, admin, event_row, stand_row):
    data = {"stand_id": stand_row["id"], "row_index": 0, "col_index": 0, "student_name": "นาย ข"}
    assert client.post(f"/api/v1/events/{event_row['id']}/rosters", json=data,
                       headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 200
    r = client.post(f"/api/v1/events/{event_row['id']}/rosters", json=data,
                    headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_roster_out_of_bounds(client, admin, event_row, stand_row):
    r = client.post(f"/api/v1/events/{event_row['id']}/rosters",
                    json={"stand_id": stand_row["id"], "row_index": 99, "col_index": 0,
                          "student_name": "นาย ค"},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_csv_import(client, admin, event_row, stand_row):
    csv_content = "row,col,student_code,student_name\n1,1,10001,นาย ก\n2,3,10002,นาย ข\n"
    r = client.post(f"/api/v1/events/{event_row['id']}/rosters/import",
                    data={"stand_id": str(stand_row["id"])},
                    files={"file": ("r.csv", csv_content.encode(), "text/csv")},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text
    assert r.json()["inserted"] == 2
