import json
import os

import asyncpg

from core.config import settings
from core.exceptions import ForbiddenError

# สิทธิ์ทั้งหมดของ Pixel Stand (3 roles → ~10 perms — ตาม design report §3)
AVAILABLE_PERMISSIONS = [
    "MANAGE_USERS",      # admin: จัดการ user/role
    "MANAGE_EVENTS",     # admin: event CRUD + duplicate + publish
    "MANAGE_STANDS",     # admin: ตั้งค่าแสตน + blocked seats
    "MANAGE_PALETTES",   # admin/designer: ชุดสี
    "MANAGE_STUNTS",     # designer: ภาพ/ฉาก CRUD + reorder
    "MANAGE_REVISIONS",  # designer: รีวิชัน/restore
    "PUBLISH_STUNTS",    # admin/designer: เผยแพร่โพย
    "CONTROL_LIVE",      # staff: คุมคิวสด
    "MANAGE_ROSTERS",    # staff: import รายชื่อที่นั่ง
    "EXPORT",            # staff: export PDF/CSV/ZIP
    "VIEW_AUDIT_LOG",    # admin: ดูบันทึกการใช้งาน
]


async def get_user_role(conn: asyncpg.Connection, user_id: int):
    row = await conn.fetchrow(
        "SELECT role FROM users WHERE id = $1 AND deleted_at IS NULL",
        int(user_id),
    )
    return row["role"] if row else None


async def require_permission(conn: asyncpg.Connection, user_id: int, required_permission: str):
    """RBAC: SUPER_ADMIN_ID ผ่านฉลุย · role ที่ is_admin ผ่านฉลุย · ไม่งั้นเช็ค permission จาก roles.json."""
    if settings.SUPER_ADMIN_ID and int(user_id) == int(settings.SUPER_ADMIN_ID):
        return True

    role = await get_user_role(conn, user_id)
    if role is None:
        raise ForbiddenError("Access Denied: ไม่พบผู้ใช้")
    info = get_role_info(role)
    if info["is_admin"]:
        return True
    if required_permission not in info["permissions"]:
        raise ForbiddenError(f"Access Denied: คุณไม่มีสิทธิ์ '{required_permission}'")
    return True


async def require_any_permission(conn: asyncpg.Connection, user_id: int, required_permissions: list):
    """ผ่านถ้ามีสิทธิ์อย่างน้อยหนึ่งตัว (ใช้กับ internal read เช่น ดู reference image)."""
    if settings.SUPER_ADMIN_ID and int(user_id) == int(settings.SUPER_ADMIN_ID):
        return True

    role = await get_user_role(conn, user_id)
    if role is None:
        raise ForbiddenError("Access Denied: ไม่พบผู้ใช้")
    info = get_role_info(role)
    if info["is_admin"]:
        return True
    if not any(p in info["permissions"] for p in required_permissions):
        raise ForbiddenError(
            f"Access Denied: คุณไม่มีสิทธิ์ (ต้องการอย่างน้อยหนึ่ง: {', '.join(required_permissions)})"
        )
    return True


# แคช roles (อ่าน config/roles.json ครั้งเดียว)
_ROLE_CACHE = None


def _load_roles() -> dict:
    global _ROLE_CACHE
    if _ROLE_CACHE is None:
        roles_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "roles.json",
        )
        try:
            with open(roles_path, encoding="utf-8") as f:
                _ROLE_CACHE = json.load(f).get("roles", {})
        except Exception:
            _ROLE_CACHE = {}
    return _ROLE_CACHE


def get_role_info(role: str) -> dict:
    data = _load_roles().get(role, {})
    return {
        "label": data.get("label", role),
        "is_admin": bool(data.get("is_admin", False)),
        "permissions": list(data.get("permissions", [])),
    }


def get_role_permissions(role: str) -> list:
    return get_role_info(role)["permissions"]


def get_role_is_admin(role: str) -> bool:
    return get_role_info(role)["is_admin"]
