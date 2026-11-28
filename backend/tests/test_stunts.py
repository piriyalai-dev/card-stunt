"""Stunt grid validation + revisions + restore."""
import os

import pytest

from core import media


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
async def test_get_grid_round_trip(client, admin, event_row, stand_row, palette_row):
    """Studio ต้องโหลด grid เดิมได้ — endpoint นี้คือคู่ของ PUT /grid."""
    color_a = palette_row["colors"][0]["id"]
    s = client.post(f"/api/v1/events/{event_row['id']}/stunts",
                    json={"code": "S1", "title": "ฉาก", "palette_a_id": palette_row["id"]},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    sid = s.json()["id"]

    # ยังไม่เคยบันทึก → array ว่าง
    r = client.get(f"/api/v1/stunts/{sid}/grid",
                   headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text
    assert r.json()["grid_data_a"] == []
    assert r.json()["grid_width"] == 165

    g = [color_a] * (165 * 45)
    assert client.put(f"/api/v1/stunts/{sid}/grid", json={"grid_data_a": g},
                      headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 200

    r = client.get(f"/api/v1/stunts/{sid}/grid",
                   headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text
    assert r.json()["grid_data_a"] == g


@pytest.mark.asyncio
async def test_stats_counts_grid(client, admin, event_row, stand_row, palette_row):
    """REGRESSION: stats เคย 500 เพราะอ่าน grid_data จาก query ที่ไม่ได้ select."""
    color_a = palette_row["colors"][0]["id"]
    color_b = palette_row["colors"][1]["id"]
    s = client.post(f"/api/v1/events/{event_row['id']}/stunts",
                    json={"code": "S1", "title": "ฉาก", "palette_a_id": palette_row["id"]},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    sid = s.json()["id"]
    grid = [color_a, color_a, None, color_b] + [None] * (165 * 45 - 4)
    assert client.put(f"/api/v1/stunts/{sid}/grid", json={"grid_data_a": grid},
                      headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 200
    r = client.get(f"/api/v1/stunts/{sid}/stats",
                   headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["filled_a"] == 3
    assert body["color_counts_a"][str(color_a)] == 2
    assert body["color_counts_a"][str(color_b)] == 1
    assert body["total_cells"] == 165 * 45


@pytest.mark.asyncio
async def test_get_grid_unknown_stunt_404(client, admin):
    r = client.get("/api/v1/stunts/999999/grid",
                   headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 404


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


@pytest.mark.asyncio
async def test_delete_stunt_removes_media_files(client, admin, event_row, stand_row, palette_row):
    """delete_stunt ต้องลบไฟล์ media (reference/thumb) ด้วย — กัน orphan บนดิสก์."""
    s = client.post(f"/api/v1/events/{event_row['id']}/stunts",
                    json={"code": "S1", "title": "ฉาก", "palette_a_id": palette_row["id"]},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    sid = s.json()["id"]

    # จำลอง stunt ที่เคยอัปโหลด reference image ไว้
    ref = media._safe_path(sid, "reference.png")
    os.makedirs(os.path.dirname(ref), exist_ok=True)
    with open(ref, "wb") as f:
        f.write(b"fake")
    assert os.path.exists(ref)

    r = client.delete(f"/api/v1/stunts/{sid}",
                      headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text

    assert not os.path.exists(os.path.dirname(ref))
