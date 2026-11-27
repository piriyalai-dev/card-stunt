"""
📡 Request Context — เก็บข้อมูลของ request/งานปัจจุบัน (contextvar)

ใช้ให้ AuditLogger เก็บ ip_address / user_agent / endpoint_or_command / trace_id /
execution_time_ms อัตโนมัติโดยไม่ต้องแก้ signature ของ service ทุกตัว (ลอกแบบ prsc_portal):
- HTTP: middleware ใน main.py ตั้ง context ตอนรับ request → services/logger อ่านได้
- งานที่ไม่ผ่าน HTTP (ARQ worker / script): ครอบด้วย `audit_scope()`
- จบงาน → clear (กัน leak ข้าม request)

⚠️ ทุกคอลัมน์ของ audit_logs ต้องไม่เว้นว่าง — context ที่ว่างคือต้นเหตุที่ค่าเป็น NULL
"""
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Dict, Iterator, Optional

_AUDIT_CTX: ContextVar[Dict] = ContextVar("audit_ctx", default={})


def set_audit_context(
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    trace_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    started_at: Optional[float] = None,
) -> None:
    _AUDIT_CTX.set({
        "ip_address": ip_address,
        "user_agent": user_agent,
        "trace_id": trace_id,
        "endpoint": endpoint,
        "started_at": time.monotonic() if started_at is None else started_at,
    })


def get_audit_context() -> Dict:
    return _AUDIT_CTX.get()


def clear_audit_context() -> None:
    _AUDIT_CTX.set({})


@contextmanager
def audit_scope(
    endpoint: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> Iterator[Dict]:
    """ครอบงานที่ไม่ได้ผ่าน HTTP ให้มี audit context เหมือน request"""
    previous = _AUDIT_CTX.get()
    set_audit_context(
        ip_address=ip_address,
        user_agent=user_agent,
        trace_id=trace_id or str(uuid.uuid4()),
        endpoint=endpoint,
    )
    try:
        yield _AUDIT_CTX.get()
    finally:
        _AUDIT_CTX.set(previous)
