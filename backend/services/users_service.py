import asyncpg

from core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from core.logger import AuditLogger
from core.rbac import get_role_permissions, get_role_is_admin, require_permission
from services.auth_service import hash_password

VALID_ROLES = ("admin", "designer", "staff")


def _row_to_out(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "role": row["role"],
        "is_admin": get_role_is_admin(row["role"]),
        "permissions": get_role_permissions(row["role"]),
        "must_change_password": bool(row["must_change_password"]),
    }


async def list_users(pool: asyncpg.Pool, user_id: int) -> list:
    async with pool.acquire() as conn:
        await require_permission(conn, user_id, "MANAGE_USERS")
        rows = await conn.fetch(
            "SELECT id, username, display_name, role, must_change_password"
            " FROM users WHERE deleted_at IS NULL ORDER BY id"
        )
    return [_row_to_out(r) for r in rows]


async def create_user(pool: asyncpg.Pool, actor_id: int, data: dict) -> dict:
    if data["role"] not in VALID_ROLES:
        raise ValidationError("role ไม่ถูกต้อง")
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_USERS")
            try:
                uid = await conn.fetchval(
                    "INSERT INTO users (username, password_hash, display_name, role)"
                    " VALUES ($1, $2, $3, $4) RETURNING id",
                    data["username"], hash_password(data["password"]),
                    data.get("display_name"), data["role"],
                )
            except asyncpg.UniqueViolationError:
                raise ConflictError("username นี้ถูกใช้แล้ว")
            await AuditLogger("users").log(
                conn, "CREATE_USER", str(actor_id), "web",
                user_id=actor_id, entity_type="user", entity_id=str(uid),
                new_values={"username": data["username"], "role": data["role"]},
            )
            row = await conn.fetchrow(
                "SELECT id, username, display_name, role, must_change_password"
                " FROM users WHERE id = $1", uid,
            )
    return _row_to_out(row)


async def update_user(pool: asyncpg.Pool, actor_id: int, user_id: int, data: dict) -> dict:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_USERS")
            row = await conn.fetchrow(
                "SELECT id, role FROM users WHERE id = $1 AND deleted_at IS NULL", user_id,
            )
            if not row:
                raise NotFoundError("ไม่พบผู้ใช้")

            new_role = data.get("role")
            if new_role is not None and new_role not in VALID_ROLES:
                raise ValidationError("role ไม่ถูกต้อง")
            # กัน demote/ลบ admin คนสุดท้าย
            if new_role is not None and new_role != row["role"] and row["role"] == "admin":
                if not await _has_other_admin(conn, user_id):
                    raise ConflictError("ไม่สามารถเปลี่ยน role ของ admin คนสุดท้าย")

            sets, params = [], []
            for col in ("display_name", "role"):
                if col in data and data[col] is not None:
                    params.append(data[col])
                    sets.append(f"{col} = ${len(params)}")
            if data.get("password"):
                params.append(hash_password(data["password"]))
                sets.append(f"password_hash = ${len(params)}")
                params.append(False)
                sets.append(f"must_change_password = ${len(params)}")
            if sets:
                sets.append("updated_at = NOW()")
                params.append(user_id)
                await conn.execute(
                    f"UPDATE users SET {', '.join(sets)} WHERE id = ${len(params)}", *params,
                )
            await AuditLogger("users").log(
                conn, "UPDATE_USER", str(actor_id), "web",
                user_id=actor_id, entity_type="user", entity_id=str(user_id),
                old_values={"role": row["role"]}, new_values=data,
            )
            updated = await conn.fetchrow(
                "SELECT id, username, display_name, role, must_change_password"
                " FROM users WHERE id = $1", user_id,
            )
    return _row_to_out(updated)


async def delete_user(pool: asyncpg.Pool, actor_id: int, user_id: int) -> None:
    if actor_id == user_id:
        raise ConflictError("ไม่สามารถลบบัญชีตัวเอง")
    async with pool.acquire() as conn:
        async with conn.transaction():
            await require_permission(conn, actor_id, "MANAGE_USERS")
            row = await conn.fetchrow(
                "SELECT id, role FROM users WHERE id = $1 AND deleted_at IS NULL", user_id,
            )
            if not row:
                raise NotFoundError("ไม่พบผู้ใช้")
            if row["role"] == "admin" and not await _has_other_admin(conn, user_id):
                raise ConflictError("ไม่สามารถลบ admin คนสุดท้าย")
            await conn.execute(
                "UPDATE users SET deleted_at = NOW() WHERE id = $1", user_id,
            )
            await AuditLogger("users").log(
                conn, "DELETE_USER", str(actor_id), "web",
                user_id=actor_id, entity_type="user", entity_id=str(user_id),
                old_values={"username": row["id"]},
            )


async def _has_other_admin(conn: asyncpg.Connection, exclude_id: int) -> bool:
    return bool(await conn.fetchval(
        "SELECT 1 FROM users WHERE role = 'admin' AND deleted_at IS NULL AND id <> $1 LIMIT 1",
        exclude_id,
    ))
