import json
import time
import uuid

import asyncpg
from typing import Optional, Dict

from core.request_context import get_audit_context

# 🧩 ค่าที่ใช้แทน "ไม่มีข้อมูล" — audit_logs ห้ามเว้นว่าง (NULL) เด็ดขาด
UNKNOWN = "-"        # คอลัมน์ข้อความ: ไม่ทราบค่า/ไม่มีค่า ณ ขณะบันทึก
EMPTY_JSON = {}      # คอลัมน์ JSONB: ไม่มีข้อมูล old/new (เช่น action ประเภทอ่าน)
UNRESOLVED_ID = -1   # user_id: ไม่รู้จักตัวตน (ไม่มี FK ในตารางนี้แล้ว)


def _clean_ip(value: Optional[str]) -> Optional[str]:
    """ทำ IP ให้เป็นรูปเดียว — ตัด port, ตัด prefix IPv6-mapped"""
    if not value:
        return None
    ip = value.strip()
    if not ip:
        return None
    if ip.startswith("[") and "]" in ip:
        ip = ip[1:ip.index("]")]
    elif ip.count(":") == 1 and "." in ip:
        ip = ip.split(":")[0]
    if ip.lower().startswith("::ffff:"):
        ip = ip[7:]
    return ip[:45] or None


def _text(value, default: str = UNKNOWN) -> str:
    if value is None:
        return default
    value = str(value).strip()
    return value or default


class AuditLogger:
    """บันทึก Audit Log ทุกการ CREATE/UPDATE/DELETE ภายใน Transaction เดียวกับข้อมูลหลัก.

    📌 สัญญา: "ทุกคอลัมน์ถูกบันทึกเสมอ" (ไม่เว้นว่าง) — ค่าที่ caller ไม่ส่ง จะถูกเติมจาก
    request context → ค่า sentinel (ไม่มี room scope เพราะ card-stunt ไม่มีห้องเรียน)
    """

    def __init__(self, service_name: str):
        self.service_name = service_name

    async def log(
        self,
        conn: asyncpg.Connection,
        action: str,
        actor_identifier: str,
        client_source: str,
        user_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        status: str = 'success',
        error_detail: Optional[str] = None,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        endpoint_or_command: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        trace_id: Optional[str] = None,
    ):
        ctx = get_audit_context()

        current_ip = _clean_ip(ip_address) or _clean_ip(ctx.get("ip_address")) or UNKNOWN
        current_ua = _text(user_agent) if user_agent else _text(ctx.get("user_agent"))
        current_trace_id = _text(trace_id) if trace_id else _text(ctx.get("trace_id")) or str(uuid.uuid4())

        current_endpoint = (
            _text(ctx.get("endpoint")) if ctx.get("endpoint")
            else _text(endpoint_or_command) if endpoint_or_command
            else f"{_text(client_source, 'unknown')}:{_text(action)}"
        )

        current_exec_ms = execution_time_ms
        if current_exec_ms is None:
            started_at = ctx.get("started_at")
            current_exec_ms = max(0, int((time.monotonic() - started_at) * 1000)) if started_at else 0
        current_exec_ms = max(0, int(current_exec_ms))

        current_user_id = UNRESOLVED_ID if user_id is None else int(user_id)

        await conn.execute("""
            INSERT INTO audit_logs (
                trace_id, user_id, actor_identifier, client_source,
                service_name, action, entity_type, entity_id, status,
                error_detail, old_values, new_values, endpoint_or_command,
                ip_address, user_agent, execution_time_ms
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12::jsonb, $13, $14, $15, $16)
        """,
            current_trace_id, current_user_id,
            _text(actor_identifier), _text(client_source),
            _text(self.service_name), _text(action), _text(entity_type),
            _text(entity_id),
            _text(status, 'success'), _text(error_detail),
            json.dumps(old_values, default=str) if old_values else json.dumps(EMPTY_JSON),
            json.dumps(new_values, default=str) if new_values else json.dumps(EMPTY_JSON),
            current_endpoint, current_ip, current_ua, current_exec_ms,
        )
