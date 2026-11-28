"""
⏱️ Redis cache + ETag สำหรับ public endpoints (design §4: cache รองรับ 1,000+ concurrent)

หลักการ:
- Redis **ว่าง/ล่ม = cache miss** แล้วอ่านจาก DB ตรง ๆ — ห้าม 500 ห้าม block startup
- invalidation แบบ version-based: key ฝัง `event.version` (gen) ⇒ แก้/publish event บั๊ม version
  แล้ว key เก่าหมดอายุเองตาม TTL ไม่ต้อง SCAN/DEL
- loop-safe: TestClient สร้าง event loop ใหม่ต่อ test ⇒ client ที่ผูก loop เก่าต้องสร้างใหม่
"""
import asyncio
import json
import logging

logger = logging.getLogger("CACHE")

_PREFIX = "pixelstand"
_client = None
_client_loop = None


def _redis():
    """คืน redis.asyncio client (สร้างครั้งแรกต่อ event loop) หรือ None ถ้าไม่มี REDIS_URL."""
    from core.config import settings
    global _client, _client_loop

    if not settings.REDIS_URL:
        return None

    loop = asyncio.get_running_loop()
    if _client is None or _client_loop is not loop:
        # loop เปลี่ยน (TestClient สร้าง loop ใหม่ต่อ test) — client เก่าผูก loop ตายแล้ว
        # ปล่อยให้ GC เก็บ (ปิดแบบ await ไม่ได้ข้าม loop) แล้วสร้างใหม่
        _client = None
        import redis.asyncio as aioredis
        _client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        _client_loop = loop
    return _client


async def _safe_call(coro):
    """ครอบทุก call — RedisError/ConnectionError = None (cache miss)."""
    try:
        return await coro
    except Exception as e:  # noqa: BLE001 — Redis เป็น optional ถ้าไม่พร้อมก็ข้าม
        logger.debug("redis unavailable: %s", e)
        return None


async def get_json(key: str):
    r = _redis()
    if r is None:
        return None
    raw = await _safe_call(r.get(key))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


async def set_json(key: str, value, ttl: int) -> None:
    r = _redis()
    if r is None:
        return
    await _safe_call(r.set(key, json.dumps(value, ensure_ascii=False, default=str), ex=ttl))


async def flush_test_db() -> None:
    """ล้าง DB ของเทสต์ก่อนแต่ละ test (Redis db 15) — ไม่แตะ db production (1)."""
    r = _redis()
    if r is None:
        return
    await _safe_call(r.flushdb())


# ── key helper ──────────────────────────────────────────────────────

def cache_key(slug: str, gen: int, kind: str, *parts) -> str:
    seg = ":".join(parts)
    return f"{_PREFIX}:cache:public:{kind}:{slug}:g{gen}" + (f":{seg}" if seg else "")


def etag_for(body) -> str:
    """strong ETag จาก canonical JSON ของ body."""
    import hashlib
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f'"ps-{hashlib.sha256(canon.encode("utf-8")).hexdigest()[:32]}"'
