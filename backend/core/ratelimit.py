"""
🚦 Rate limiting สำหรับ login — กัน brute-force (Fixed window)

- Redis (ถ้า `REDIS_URL` มีค่า): `INCR` + `EXPIRE` — แชร์ counter ข้าม process
- in-memory fallback: เมื่อ Redis ว่าง/ล่ม → degrade อย่างปลอดภัย (ลอกแนวคิด core/cache)
  ⚠️ in-memory เป็น per-process (replicas:1 ในตอนนี้ ⇒ OK)
"""
import time

from core.config import settings
from core.exceptions import RateLimitError

# in-memory fallback: {key: (window_start_monotonic, count)}
_mem: dict[str, tuple[float, int]] = {}


def _mem_incr_window(key: str, window_seconds: int, limit: int) -> bool:
    """in-memory fixed window — คืน True ถ้าเกิน limit."""
    now = time.monotonic()
    start, count = _mem.get(key, (now, 0))
    if now - start >= window_seconds:
        start, count = now, 0
    count += 1
    _mem[key] = (start, count)
    return count > limit


async def _incr_window(key: str, window_seconds: int, limit: int) -> bool:
    """Redis fixed window ถ้ามี Redis · ไม่งั้น in-memory. คืน True ถ้าเกิน limit."""
    from core.cache import _redis

    r = _redis()
    if r is None:
        return _mem_incr_window(key, window_seconds, limit)
    try:
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, window_seconds)
        return count > limit
    except Exception:  # noqa: BLE001 — Redis ล่ม = ลดขั้นเป็น in-memory ไม่ block login
        return _mem_incr_window(key, window_seconds, limit)


async def check_login_rate_limit(ip: str, username: str) -> None:
    """ตรวจทั้ง per-IP และ per-username — เกินเพดานตัวใดตัวหนึ่ง → RateLimitError (429)."""
    limit = settings.LOGIN_RATE_LIMIT_MAX
    window = settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
    ip = ip or "unknown"
    for key in (f"pixelstand:ratelimit:login:ip:{ip}", f"pixelstand:ratelimit:login:user:{username}"):
        if await _incr_window(key, window, limit):
            raise RateLimitError(f"พยายามเข้าสู่ระบบบ่อยเกินไป — ลองใหม่ใน {max(1, window // 60)} นาที")


def reset() -> None:
    """ล้าง in-memory fallback — ใช้ใน test fixture (Redis ฝั่งเทสต์ถูกล้างด้วย flushdb อยู่แล้ว)."""
    _mem.clear()
