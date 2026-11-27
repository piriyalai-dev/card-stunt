"""Stunt grid validation + revisions + restore."""
import pytest


@pytest.mark.asyncio
async def test_create_stunt_shell(client, admin, event_row, stand_row, palette_row):
    r = client.post(f"/api/v1/events/{event_row['id']}/stunts",
                    json={"code": "S1", "title": "ฉาก 1", "palette_a_id": palette_row["id"]},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text
    assert r.json()["grid_width"] == 165
    assert r.json()["grid_height"] == 45


@pytest.mark.asyncio
async def test_grid_validation(client, admin, event_row, stand_row, palette_row):
    s = client.post(f"/api/v1/events/{event_row['id']}/stunts",
                    json={"code": "S1", "title": "ฉาก", "palette_a_id": palette_row["id"]},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    sid = s.json()["id"]
    # ยาวผิด → 400
    r = client.put(f"/api/v1/stunts/{sid}/grid", json={"grid_data_a": [1, 2, 3]},
                   headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 400
    # สีไม่อยู่ใน palette → 400
    r = client.put(f"/api/v1/stunts/{sid}/grid", json={"grid_data_a": [999] * (165 * 45)},
                   headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_revisions_snapshot_and_restore(client, admin, event_row, stand_row, palette_row):
    color_a = palette_row["colors"][0]["id"]
    color_b = palette_row["colors"][1]["id"]
    s = client.post(f"/api/v1/events/{event_row['id']}/stunts",
                    json={"code": "S1", "title": "ฉาก", "palette_a_id": palette_row["id"]},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    sid = s.json()["id"]
    # save v1 (all color_a) → สร้าง revision 1
    g1 = [color_a] * (165 * 45)
    assert client.put(f"/api/v1/stunts/{sid}/grid", json={"grid_data_a": g1},
                      headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 200
    # save v2 (all color_b) → revision 2
    g2 = [color_b] * (165 * 45)
    assert client.put(f"/api/v1/stunts/{sid}/grid", json={"grid_data_a": g2},
                      headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 200

    revs = client.get(f"/api/v1/stunts/{sid}/revisions",
                      headers={"Authorization": f"Bearer {admin['token']}"}).json()
    assert len(revs) >= 2
    # restore rev ที่เป็น g1
    rev1 = [r for r in revs if r["revision_no"] == 1][0]
    assert client.post(f"/api/v1/stunts/{sid}/revisions/{rev1['id']}/restore",
                       headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 200
