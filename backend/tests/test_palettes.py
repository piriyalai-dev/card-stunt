"""Palette + colors + used-color delete guard."""
import pytest


@pytest.mark.asyncio
async def test_create_palette_with_colors(client, admin, event_row):
    r = client.post(f"/api/v1/events/{event_row['id']}/palettes",
                    json={"name": "ชุดสี", "colors": [{"code": "01", "name_th": "แดง", "hex": "#B91C1C"}]},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text
    assert len(r.json()["colors"]) == 1


@pytest.mark.asyncio
async def test_duplicate_color_code(client, admin, palette_row):
    pid = palette_row["id"]
    r = client.post(f"/api/v1/palettes/{pid}/colors",
                    json={"code": "01", "name_th": "แดงอีก", "hex": "#991B1B"},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_hex_validation(client, admin, palette_row):
    r = client.post(f"/api/v1/palettes/{palette_row['id']}/colors",
                    json={"code": "99", "name_th": "x", "hex": "red"},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_delete_color_used_by_grid_requires_replacement(client, admin, event_with_palettes, stand_row, palette_row):
    color_id = palette_row["colors"][0]["id"]
    # สร้าง stunt + grid ใช้สีนี้
    s = client.post(f"/api/v1/events/{event_with_palettes['id']}/stunts",
                    json={"code": "S1", "title": "ฉาก", "side": "A"},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    assert s.status_code == 200, s.text
    stunt_id = s.json()["id"]
    grid = [color_id] * (165 * 45)
    assert client.put(f"/api/v1/stunts/{stunt_id}/grid", json={"grid_data": grid},
                      headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 200
    # ลบสีโดยไม่มี replacement → 409 (DELETE + body ใช้ request() เพราะ client.delete ไม่มี json=)
    r = client.request("DELETE", f"/api/v1/palettes/{palette_row['id']}/colors/{color_id}",
                       json={}, headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_delete_palette_blocked_when_event_palette(client, admin, event_with_palettes, stand_row, palette_row):
    """palette ที่ถูกใช้เป็นชุดสี A/B ของ event → ลบไม่ได้ (409)."""
    r = client.delete(f"/api/v1/palettes/{palette_row['id']}",
                      headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 409
