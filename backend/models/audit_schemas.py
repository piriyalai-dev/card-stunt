from typing import Any, List, Optional

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    trace_id: Optional[str] = None
    user_id: Optional[int] = None
    actor_identifier: str
    client_source: str
    service_name: str
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    status: str = "success"
    error_detail: Optional[str] = None
    old_values: Optional[Any] = None
    new_values: Optional[Any] = None
    endpoint_or_command: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    execution_time_ms: Optional[int] = None
    created_at: Any


class AuditLogPage(BaseModel):
    items: List[AuditLogOut]
    next_cursor: Optional[str] = None
    has_more: bool = False


class AuditLogOptions(BaseModel):
    actions: List[str]
    statuses: List[str]
    entity_types: List[str]
    service_names: List[str]
