"""Live sync: advance RBAC + PG NOTIFY trigger + hub + SSE."""
import asyncio
import json

import asyncpg
import pytest
import pytest_asyncio

from core.config import settings
from core.live_stream import LiveHub, StreamAtCapacity
from main import app


async def _publish(client, admin, event_row, stand_row, palette_row, count=3):
    """สร้าง + publish event พร้อม stunts จำนวน count."""
    for i in range(count):
        assert client.post(f"/api/v1/events/{event_row['id']}/stunts",
                           json={"code": f"S{i}", "title": f"ฉาก {i}"},
                           headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 200
    assert client.post(f"/api/v1/events/{event_row['id']}/publish",
                       headers={"Authorization": f"Bearer {admin['token']}"}).status_code == 200


@pytest.mark.asyncio
async def test_advance_next_prev(client, admin, event_row, stand_row, palette_row):
    await _publish(client, admin, event_row, stand_row, palette_row)
    r = client.post(f"/api/v1/events/{event_row['id']}/live/advance", json={"action": "next"},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.status_code == 200, r.text
    assert r.json()["current_index"] == 1
    r = client.post(f"/api/v1/events/{event_row['id']}/live/advance", json={"action": "prev"},
                    headers={"Authorization": f"Bearer {admin['token']}"})
    assert r.json()["current_index"] == 0


@pytest.mark.asyncio
async def test_advance_rbac(client, admin, designer, staff, event_row, stand_row, palette_row):
    await _publish(client, admin, event_row, stand_row, palette_row, count=1)
    # staff (CONTROL_LIVE) ทำได้
    assert client.post(f"/api/v1/events/{event_row['id']}/live/advance", json={"action": "next"},
                       headers={"Authorization": f"Bearer {staff['token']}"}).status_code == 200
    # designer (ไม่มี CONTROL_LIVE) ทำไม่ได้
    assert client.post(f"/api/v1/events/{event_row['id']}/live/advance", json={"action": "next"},
                       headers={"Authorization": f"Bearer {designer['token']}"}).status_code == 403


# ── trigger: pg_notify ตอน commit เท่านั้น ──────────────────────────

async def _listen(dsn, channel):
    conn = await asyncpg.connect(dsn)
    received = []
    await conn.add_listener(channel, lambda _c, _p, _ch, payload: received.append(payload))
    return conn, received


@pytest.mark.asyncio
async def test_trigger_notify_on_commit(client, admin, event_row, stand_row, palette_row, test_db_url):
    await _publish(client, admin, event_row, stand_row, palette_row)
    conn, received = await _listen(test_db_url, settings.NOTIFY_CHANNEL)
    try:
        client.post(f"/api/v1/events/{event_row['id']}/live/advance", json={"action": "next"},
                    headers={"Authorization": f"Bearer {admin['token']}"})
        deadline = asyncio.get_running_loop().time() + 5
        while not received and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.02)
        assert received
        data = json.loads(received[0])
        assert data["slug"] == "sport69"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_trigger_no_notify_on_rollback(db_pool, test_db_url):
    conn, received = await _listen(test_db_url, settings.NOTIFY_CHANNEL)
    try:
        async with db_pool.acquire() as c:
            await c.execute("INSERT INTO events (slug, name) VALUES ('rollback-test', 'x')")
            eid = await c.fetchval("SELECT id FROM events WHERE slug = 'rollback-test'")
        # UPDATE live_stunt_id แล้ว rollback → ต้องไม่ยิง NOTIFY
        try:
            async with db_pool.acquire() as c:
                async with c.transaction():
                    await c.execute("UPDATE events SET live_stunt_id = 999 WHERE id = $1", eid)
                    raise RuntimeError("force rollback")
        except RuntimeError:
            pass
        await asyncio.sleep(0.2)
        assert received == []
    finally:
        await conn.close()


# ── hub (in-memory) ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_hub_subscribe_publish():
    h = LiveHub(channel="x", max_subscribers=2)
    q = h.subscribe("slug-a")
    h._publish("slug-a")
    assert q.get_nowait() is None
    h.unsubscribe("slug-a", q)
    assert h.subscriber_count == 0


@pytest.mark.asyncio
async def test_hub_capacity():
    h = LiveHub(channel="x", max_subscribers=1)
    h.subscribe("a")
    assert h.at_capacity("b") is True
    with pytest.raises(StreamAtCapacity):
        h.subscribe("b")


# ── SSE endpoint (raw ASGI driver — TestClient deadlocks) ──────────

class _Sse:
    def __init__(self, path):
        self.scope = {
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": "GET", "scheme": "http",
            "path": path, "raw_path": path.encode(), "query_string": b"",
            "root_path": "", "headers": [(b"host", b"test")],
            "client": ("test", 50000), "server": ("test", 80),
        }
        self.messages = asyncio.Queue()
        self._connected = True

    async def receive(self):
        if not self._connected:
            return {"type": "http.disconnect"}
        await asyncio.sleep(0.05)
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(self, msg):
        await self.messages.put(msg)

    def disconnect(self):
        self._connected = False


@pytest.mark.asyncio
async def test_sse_snapshot(client, admin, event_row, stand_row, palette_row, test_db_url):
    await _publish(client, admin, event_row, stand_row, palette_row)
    # ยัด db_pool ของเทสต์เข้า app.state (single pool — ตรงกับ prsc เทคนิค)
    prev = getattr(app.state, "db_pool", None)
    app.state.db_pool = await asyncpg.create_pool(test_db_url)
    sse = _Sse("/api/v1/public/events/sport69/live")
    task = asyncio.ensure_future(app(sse.scope, sse.receive, sse.send))
    try:
        # อ่าน frame แรก (snapshot) ก่อน disconnect — เช็คแค่ type + body ไม่ผูก header ตำแหน่ง
        msg = await asyncio.wait_for(sse.messages.get(), timeout=5)
        assert msg["type"] == "http.response.start"
        body_msg = await asyncio.wait_for(sse.messages.get(), timeout=5)
        data = body_msg.get("body", b"").decode()
        assert "event: snapshot" in data
        assert "current_stunt_id" in data
    finally:
        sse.disconnect()
        await asyncio.wait_for(task, timeout=5)
        await app.state.db_pool.close()
        app.state.db_pool = prev
