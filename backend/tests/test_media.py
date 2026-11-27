"""Phase 5 — media serving ผ่าน signed URL (reference image + thumbnail)."""
import io

import pytest
from PIL import Image

from core import media


def _png(size=(24, 24), color=(185, 28, 28)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _stunt(client, admin, event_row, stand_row):
    r = client.post(
        f"/api/v1/events/{event_row['id']}/stunts",
        json={"code": "M1", "title": "รูปอ้างอิง", "stand_id": stand_row["id"]},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_upload_then_signed_url_serves_image(client, admin, event_row, stand_row):
    sid = _stunt(client, admin, event_row, stand_row)
    up = client.post(
        f"/api/v1/stunts/{sid}/reference-image",
        files={"file": ("ref.png", _png(), "image/png")},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert up.status_code == 200, up.text

    resp = client.get(
        f"/api/v1/stunts/{sid}/media-urls",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert resp.status_code == 200, resp.text
    urls = resp.json()
    assert urls["reference_url"] and urls["thumbnail_url"]

    r = client.get(urls["reference_url"])
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")
    assert r.content == _png()

    thumb = client.get(urls["thumbnail_url"])
    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/webp"


@pytest.mark.asyncio
async def test_media_urls_without_file_return_null(client, admin, event_row, stand_row):
    sid = _stunt(client, admin, event_row, stand_row)
    urls = client.get(
        f"/api/v1/stunts/{sid}/media-urls",
        headers={"Authorization": f"Bearer {admin['token']}"},
    ).json()
    assert urls == {"reference_url": None, "thumbnail_url": None}


def test_signed_url_rejects_tampering_and_expiry():
    url = media.signed_url("stunts/1/reference.png", ttl=60)
    assert url
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(url)
    exp = int(parse_qs(parsed.query)["exp"][0])
    sig = parse_qs(parsed.query)["sig"][0]

    assert media.verify_signed_path("stunts/1/reference.png", exp, sig)

    with pytest.raises(Exception):
        media.verify_signed_path("stunts/1/reference.png", exp, sig + "x")

    expired = media.signed_url("stunts/1/reference.png", ttl=-5)
    parsed = urlparse(expired)
    with pytest.raises(Exception):
        media.verify_signed_path(
            "stunts/1/reference.png",
            int(parse_qs(parsed.query)["exp"][0]),
            parse_qs(parsed.query)["sig"][0],
        )


@pytest.mark.asyncio
async def test_media_route_rejects_bad_signature(client, event_row):
    r = client.get("/api/v1/media/stunts/1/none.png?exp=9999999999&sig=bad")
    assert r.status_code == 403
