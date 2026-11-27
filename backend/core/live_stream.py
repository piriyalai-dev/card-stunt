"""
📡 Live Sync hub — Postgres `LISTEN/NOTIFY` → SSE (design §4: channel `pixelstand_live`)

ลอกแบบ prsc_portal/services/notification_stream.py แต่ keyed ด้วย `event_slug` (public
viewer ไม่ต้อง login) แทน user_id — สถาปัตยกรรมเหมือนกันเป๊ะ:

- 1 connection ต่อโปรเซส (ไม่ใช่ต่อ viewer) — LISTEN ตัวเดียว fan-out ในหน่วยความจำ
- connection ของ listener **ต้องไม่มาจาก pool** → `asyncpg.connect()` ตรง ๆ
- event เป็น "สัญญาณ" ไม่ใช่ข้อมูล (`Queue(maxsize=1)` + ทิ้งเมื่อเต็ม) — client ไปอ่าน
  สถานะจริงจาก DB ทุกครั้งที่ถูก poke
- `_supervise()` ต่อใหม่พร้อม backoff 1→30 วิ — กันความล้มเหลวแบบเงียบ
"""
from __future__ import annotations

import asyncio
import json
import logging

import asyncpg

from core.config import settings

logger = logging.getLogger("LIVE_STREAM")

_QUEUE_MAXSIZE = 1
_RECONNECT_MIN = 1.0
_RECONNECT_MAX = 30.0


class StreamAtCapacity(RuntimeError):
    """เปิด stream เกินเพดานของโปรเซสนี้ — router แปลงเป็น 503"""


class LiveHub:
    """ทะเบียนผู้รับ SSE (keyed ด้วย event slug) + connection LISTEN ตัวเดียว."""

    def __init__(self, *, channel: str | None = None, max_subscribers: int | None = None) -> None:
        self._channel = channel or settings.NOTIFY_CHANNEL
        self._max_subscribers = max_subscribers or settings.STREAM_MAX_SUBSCRIBERS
        self._subscribers: dict[str, set[asyncio.Queue]] = {}
        self._conn: asyncpg.Connection | None = None
        self._supervisor: asyncio.Task | None = None
        self._dsn: str | None = None
        self._stopping = False
        self._conn_lost: asyncio.Event | None = None
        self._stale_dropped = 0

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def is_connected(self) -> bool:
        return self._conn is not None and not self._conn.is_closed()

    async def start(self, dsn: str) -> None:
        """เริ่ม supervisor — ไม่ raise ถ้าต่อไม่ได้ (live sync เป็นของที่ทำให้เร็วขึ้น)."""
        if self._supervisor is not None:
            return
        self._dsn = dsn
        self._stopping = False
        self._conn_lost = asyncio.Event()
        self._supervisor = asyncio.create_task(self._supervise(), name="live-stream-supervisor")
        self._supervisor.add_done_callback(self._on_supervisor_done)
        logger.info("📡 live stream: supervisor started (channel=%s)", self._channel)

    @staticmethod
    def _on_supervisor_done(task) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("🚨 live stream: supervisor ตายกลางทาง", exc_info=exc)

    async def stop(self) -> None:
        self._stopping = True
        if self._conn_lost is not None:
            self._conn_lost.set()
        if self._supervisor is not None:
            self._supervisor.cancel()
            try:
                await self._supervisor
            except asyncio.CancelledError:
                pass
            except Exception:  # noqa: BLE001
                logger.debug("📡 supervisor จบด้วย exception", exc_info=True)
            self._supervisor = None
        await self._close_conn()
        self._subscribers.clear()
        logger.info("📡 live stream: stopped")

    def at_capacity(self, slug: str) -> bool:
        if slug in self._subscribers:
            return False
        return len(self._subscribers) >= self._max_subscribers

    def subscribe(self, slug: str) -> asyncio.Queue:
        queues = self._subscribers.get(slug)
        if queues is None:
            if len(self._subscribers) >= self._max_subscribers:
                logger.warning("📡 live stream: ถึงเพดานผู้ฟัง (%d)", self._max_subscribers)
                raise StreamAtCapacity(f"เปิด stream พร้อมกันเกินเพดาน ({self._max_subscribers})")
            queues = set()
            self._subscribers[slug] = queues
        q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        queues.add(q)
        return q

    def unsubscribe(self, slug: str, q: asyncio.Queue) -> None:
        queues = self._subscribers.get(slug)
        if not queues:
            return
        queues.discard(q)
        if not queues:
            self._subscribers.pop(slug, None)

    def _publish(self, slug: str) -> None:
        for q in self._subscribers.get(slug, ()):
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                self._stale_dropped += 1

    async def _on_notify(self, _conn, _pid, _channel, payload: str) -> None:
        try:
            data = json.loads(payload)
            slug = data.get("slug")
            if not isinstance(slug, str) or not slug:
                logger.warning("📡 payload ไม่มี slug: %r", payload[:120])
                return
            self._publish(slug)
        except Exception:  # noqa: BLE001 — ห้าม raise ใน callback
            logger.exception("📡 ประมวลผล NOTIFY ไม่สำเร็จ (payload=%r)", payload[:120])

    async def _open_conn(self) -> None:
        conn = await asyncpg.connect(self._dsn)
        conn.add_termination_listener(lambda _c: self._conn_lost.set())
        await conn.add_listener(self._channel, self._on_notify)
        self._conn = conn
        logger.info("📡 live stream: LISTEN %s พร้อมใช้งาน", self._channel)

    async def _close_conn(self) -> None:
        conn, self._conn = self._conn, None
        if conn is None:
            return
        try:
            if not conn.is_closed():
                await conn.remove_listener(self._channel, self._on_notify)
                await conn.close()
        except Exception:  # noqa: BLE001
            logger.debug("📡 ปิด connection listener ไม่สำเร็จ", exc_info=True)

    async def _supervise(self) -> None:
        lost = self._conn_lost
        assert lost is not None, "start() ต้องถูกเรียกก่อน _supervise()"
        delay = _RECONNECT_MIN
        while not self._stopping:
            if not self.is_connected:
                lost.clear()
                try:
                    await self._open_conn()
                    delay = _RECONNECT_MIN
                except asyncio.CancelledError:
                    raise
                except Exception as e:  # noqa: BLE001
                    logger.error("📡 ต่อ LISTEN ไม่สำเร็จ (ลองใหม่ %.0f วิ): %s", delay, e)
                    await self._sleep_or_stop(lost, delay)
                    delay = min(delay * 2, _RECONNECT_MAX)
                    continue
            await lost.wait()
            if self._stopping:
                return
            lost.clear()
            logger.warning("📡 connection listener หลุด — ต่อใหม่")
            await self._close_conn()

    async def _sleep_or_stop(self, lost: asyncio.Event, seconds: float) -> None:
        try:
            await asyncio.wait_for(lost.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass


# singleton ระดับโมดูล — main.py start/stop (เทสต์สร้าง instance ใหม่เองได้)
hub = LiveHub()
