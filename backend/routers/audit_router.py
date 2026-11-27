from datetime import date
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, Query

from core.dependencies import get_current_user, get_db_pool
from models.audit_schemas import AuditLogPage, AuditLogOptions, AuditLogOut
from services import audit_service
from routers._common import map_err, ensure_user

router = APIRouter(prefix="/audit-logs", tags=["AuditLogs"])


@router.get("", response_model=AuditLogPage)
async def list_audit_logs(
    action: Optional[str] = Query(None, max_length=50),
    entity_type: Optional[str] = Query(None, max_length=50),
    entity_id: Optional[str] = Query(None, max_length=50),
    status: Optional[str] = Query(None, max_length=20),
    service_name: Optional[str] = Query(None, max_length=50),
    q: Optional[str] = Query(None, max_length=100),
    limit: int = Query(audit_service.DEFAULT_LIMIT, ge=1, le=audit_service.MAX_LIMIT),
    cursor: Optional[str] = Query(None, max_length=300),
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    uid = ensure_user(user_ctx)
    try:
        result = await audit_service.list_audit_logs(
            pool, uid, action=action, entity_type=entity_type, entity_id=entity_id,
            status=status, service_name=service_name, q=q, limit=limit, cursor=cursor,
        )
    except Exception as e:
        raise map_err(e)
    return AuditLogPage(
        items=[AuditLogOut(**i) for i in result["items"]],
        next_cursor=result["next_cursor"],
        has_more=result["has_more"],
    )


@router.get("/options", response_model=AuditLogOptions)
async def get_options(user_ctx: dict = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_db_pool)):
    uid = ensure_user(user_ctx)
    try:
        return await audit_service.get_options(pool, uid)
    except Exception as e:
        raise map_err(e)
