"""📦 ที่เก็บไฟล์ export (PDF/CSV/ZIP) — path containment + atomic write.

`export_jobs.file_path` เก็บ **relative path** ใต้ `EXPORT_STORAGE_DIR` (ไม่ผูกกับ absolute
path ของเครื่อง) ⇒ ย้าย storage root ได้โดยไม่ต้องแก้ DB · ทุกครั้งที่ resolve ต้องอยู่ใน root
เสมอ (กัน path traversal จากค่าที่หลุดเข้า DB)
"""
import os
import uuid

from core.config import settings
from core.exceptions import NotFoundError, ValidationError


def _root() -> str:
    root = os.path.abspath(settings.EXPORT_STORAGE_DIR)
    os.makedirs(root, exist_ok=True)
    return root


def _safe(rel_path: str) -> str:
    if not rel_path:
        raise ValidationError("ไม่มี path ของไฟล์ export")
    root = _root()
    path = os.path.abspath(os.path.join(root, rel_path))
    if not path.startswith(root + os.sep):
        raise ValidationError("path ออกจาก export root")
    return path


def write(rel_path: str, content: bytes) -> str:
    """เขียนไฟล์แบบ atomic (tmp → os.replace) แล้วคืน relative path เดิม."""
    path = _safe(rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + f".{uuid.uuid4().hex}.tmp"
    with open(tmp, "wb") as f:
        f.write(content)
    os.replace(tmp, path)
    return rel_path


def resolve(rel_path: str) -> str:
    """คืน absolute path ของไฟล์ที่ **มีอยู่จริง** (ไม่งั้น NotFoundError)."""
    path = _safe(rel_path)
    if not os.path.isfile(path):
        raise NotFoundError("ไม่พบไฟล์ export (อาจถูกลบตาม retention)")
    return path
