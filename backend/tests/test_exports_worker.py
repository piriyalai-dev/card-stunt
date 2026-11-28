"""Phase 5 — export builders + worker lifecycle (PDF/CSV/ZIP) + download."""
import csv
import io
import os
import time
import zipfile

import pytest

from core.config import settings
from services import exports_service

AUTH = lambda token: {"Authorization": f"Bearer {token}"}  # noqa: E731


def _prepare_published(client, admin, event_row, stand_row, palette_row):
    """สร้างฉาก 1 ฉากที่ fill ทั้งกริด + roster ที่นั่ง A1 + publish."""
    headers = AUTH(admin["token"])
    color_a = palette_row["colors"][0]["id"]

    assert client.patch(
        f"/api/v1/events/{event_row['id']}",
        json={"palette_a_id": palette_row["id"], "palette_b_id": palette_row["id"]},
        headers=headers,
    ).status_code == 200

    stunt = client.post(
        f"/api/v1/events/{event_row['id']}/stunts",
        json={"code": "S1", "title": "เปิดตัว", "stand_id": stand_row["id"], "side": "A"},
        headers=headers,
    ).json()
    cells = stand_row["rows"] * stand_row["sub_rows"] * stand_row["cols"] * stand_row["sub_cols"]
    r = client.put(
        f"/api/v1/stunts/{stunt['id']}/grid",
        json={"grid_data": [color_a] * cells},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    roster = client.post(
        f"/api/v1/events/{event_row['id']}/rosters",
        json={"stand_id": stand_row["id"], "row_index": 0, "col_index": 0,
              "student_name": "นาย ตัวอย่าง", "student_code": "10001"},
        headers=headers,
    )
    assert roster.status_code == 200, roster.text

    assert client.post(
        f"/api/v1/events/{event_row['id']}/publish", headers=headers,
    ).status_code == 200
    return stunt


async def _run(client, admin, db_pool, event_row, fmt: str) -> tuple[int, bytes]:
    job = client.post(
        f"/api/v1/events/{event_row['id']}/exports",
        json={"format": fmt}, headers=AUTH(admin["token"]),
    ).json()
    await exports_service.run_export(db_pool, job["id"])

    status = client.get(f"/api/v1/exports/{job['id']}", headers=AUTH(admin["token"])).json()
    assert status["status"] == "done", status
    download = client.get(
        f"/api/v1/exports/{job['id']}/download", headers=AUTH(admin["token"]),
    )
    assert download.status_code == 200, download.text
    return job["id"], download.content


@pytest.mark.asyncio
async def test_pdf_export_generates_valid_file(client, admin, db_pool, event_row, stand_row, palette_row):
    _prepare_published(client, admin, event_row, stand_row, palette_row)
    _, content = await _run(client, admin, db_pool, event_row, "pdf")
    assert content[:4] == b"%PDF"
    assert len(content) > 10_000  # การ์ด 2 ใบขึ้นไป พร้อมภาพ


@pytest.mark.asyncio
async def test_csv_export_contains_seat_and_cue(client, admin, db_pool, event_row, stand_row, palette_row):
    _prepare_published(client, admin, event_row, stand_row, palette_row)
    _, content = await _run(client, admin, db_pool, event_row, "csv")
    rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
    assert rows[0][:4] == ["stand", "row", "seat", "row_index"]
    seat = next(r for r in rows[1:] if r[0] == "โซนกลาง" and r[1] == "A" and r[2] == "1")
    assert seat[5] == "10001"          # student_code
    assert seat[6] == "นาย ตัวอย่าง"   # student_name
    assert len(seat[7]) == 8           # access_code
    assert seat[8] == "S1"             # stunt_code
    assert seat[10] == "A"             # side
    assert seat[11].split()[0] == "01"  # รหัสสีช่องแรก


@pytest.mark.asyncio
async def test_zip_export_has_grid_png_and_manifest(client, admin, db_pool, event_row, stand_row, palette_row):
    _prepare_published(client, admin, event_row, stand_row, palette_row)
    _, content = await _run(client, admin, db_pool, event_row, "zip")
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        names = zf.namelist()
        assert "seats.csv" in names
        assert "manifest.json" in names
        assert any(n.startswith("stunts/01-S1") and n.endswith(".png") for n in names)


@pytest.mark.asyncio
async def test_zip_export_renders_side(client, admin, db_pool, event_row, stand_row, palette_row):
    import json

    _prepare_published(client, admin, event_row, stand_row, palette_row)
    _, content = await _run(client, admin, db_pool, event_row, "zip")
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        names = zf.namelist()
        assert "stunts/01-S1-a.png" in names
        manifest = json.loads(zf.read("manifest.json"))
        sides = {f["file"].split("/")[-1]: f.get("side") for f in manifest["files"]}
        assert sides["01-S1-a.png"] == "a"


@pytest.mark.asyncio
async def test_retry_requeues_finished_job(client, admin, db_pool, event_row, stand_row, palette_row):
    _prepare_published(client, admin, event_row, stand_row, palette_row)
    job_id, _ = await _run(client, admin, db_pool, event_row, "csv")
    r = client.post(f"/api/v1/exports/{job_id}/retry", headers=AUTH(admin["token"]))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_download_requires_done(client, admin, event_row):
    job = client.post(
        f"/api/v1/events/{event_row['id']}/exports",
        json={"format": "csv"}, headers=AUTH(admin["token"]),
    ).json()
    r = client.get(f"/api/v1/exports/{job['id']}/download", headers=AUTH(admin["token"]))
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_purge_expired_exports(client, admin, db_pool, event_row, stand_row, palette_row):
    _prepare_published(client, admin, event_row, stand_row, palette_row)
    job_id, _ = await _run(client, admin, db_pool, event_row, "csv")

    folder = os.path.join(settings.EXPORT_STORAGE_DIR, "exports", str(job_id))
    old = time.time() - (settings.EXPORT_MAX_AGE_DAYS + 1) * 86400
    os.utime(folder, (old, old))

    removed = await exports_service.purge_expired_exports(db_pool)
    assert removed == 1
    assert not os.path.isdir(folder)
    row = await db_pool.fetchrow("SELECT file_path, error FROM export_jobs WHERE id = $1", job_id)
    assert row["file_path"] is None
    assert "retention" in row["error"]

    # ไฟล์หายแล้ว → ดาวน์โหลดต้องไม่สำเร็จแบบ conflict
    r = client.get(f"/api/v1/exports/{job_id}/download", headers=AUTH(admin["token"]))
    assert r.status_code == 409
