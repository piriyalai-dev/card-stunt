"""Roster manual + CSV import + bounds/dupes."""
import io

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
    # mint รหัสล็อกอิน 8 ตัวอักษร (unique ต่อ event)
    assert len(r.json()["access_code"]) == 8


@pytest.mark.asyncio
async def test_roster_access_codes_unique(client, admin, event_row, stand_row):
    codes = set()
    for col in range(5):
        r = client.post(f"/api/v1/events/{event_row['id']}/rosters",
                        json={"stand_id": stand_row["id"], "row_index": 0, "col_index": col,
                              "student_name": f"นาย {col}"},
                        headers={"Authorization": f"Bearer {admin['token']}"})
        assert r.status_code == 200, r.text
        codes.add(r.json()["access_code"])
    assert len(codes) == 5


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


@pytest.mark.asyncio
async def test_import_rejects_legacy_xls(client, admin, event_row, stand_row):
    # openpyxl อ่าน BIFF/OLE .xls ไม่ได้ — ต้องได้ 400 ชัดเจน ไม่ใช่ 500 ดิบ
    r = client.post(f"/api/v1/events/{event_row['id']}/rosters/import",
                    data={"stand_id": str(stand_row["id"])},
                    files={"file": ("legacy.xls", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "application/vnd.ms-excel")},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 400, r.text
    assert ".xls" in r.json()["detail"]


@pytest.mark.asyncio
async def test_import_xlsx_numeric_student_code(client, admin, event_row, stand_row):
    # Excel เก็บ student_code เป็นตัวเลข (float) → ต้องได้ "40000" ไม่ใช่ "40000.0" หรือ crash
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["row", "col", "student_code", "student_name"])
    ws.append([1, 1, 40000.0, "นาย หนึ่ง"])
    buf = io.BytesIO()
    wb.save(buf)
    r = client.post(f"/api/v1/events/{event_row['id']}/rosters/import",
                    data={"stand_id": str(stand_row["id"])},
                    files={"file": ("r.xlsx", buf.getvalue(),
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text
    assert r.json()["inserted"] == 1
    rosters = client.get(f"/api/v1/events/{event_row['id']}/rosters",
                         headers={"Authorization": f"Bearer {admin['token']}"}).json()
    assert rosters[0]["student_code"] == "40000"
