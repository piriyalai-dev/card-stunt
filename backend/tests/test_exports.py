"""Export job create + status + download guard (Phase 3 — ยังไม่มี worker)."""
import pytest


@pytest.mark.asyncio
async def test_create_export_queued(client, admin, event_row):
    r = client.post(f"/api/v1/events/{event_row['id']}/exports",
                    json={"format": "pdf"},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_download_guard_not_done(client, admin, event_row):
    j = client.post(f"/api/v1/events/{event_row['id']}/exports", json={"format": "csv"},
                    headers={"Authorization": f"Bearer {admin['token']}"}).json()
    r = client.get(f"/api/v1/exports/{j['id']}/download",
                   headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 409
