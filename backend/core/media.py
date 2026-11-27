"""
🖼️ Media — เก็บ reference image + thumbnail (Phase 3; signed URL/media เต็มมา Phase 5)

- reference image เก็บที่ `MEDIA_STORAGE_DIR/stunts/<id>/reference.<ext>`
- thumbnail เก็บที่ `MEDIA_STORAGE_DIR/stunts/<id>/thumb.webp` (WebP, max 480)
- เขียนแบบ atomic (tmp → os.replace) + ตรวจ MIME/ขนาดด้วย Pillow + path containment
"""
import base64
import hashlib
import hmac
import os
import time
import uuid
from urllib.parse import quote

from core.config import settings
from core.exceptions import PayloadTooLargeError, ValidationError

ALLOWED_EXT = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}


def _root() -> str:
    root = os.path.abspath(settings.MEDIA_STORAGE_DIR)
    os.makedirs(root, exist_ok=True)
    return root


def _safe_path(stunt_id: int, name: str) -> str:
    """รับประกันว่า path อยู่ใต้ media root เสมอ (กัน path traversal)."""
    root = _root()
    path = os.path.abspath(os.path.join(root, "stunts", str(int(stunt_id)), name))
    if not path.startswith(root + os.sep):
        raise ValidationError("path ออกจาก media root")
    return path


def _ext(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower().lstrip(".")


async def save_reference(stunt_id: int, content: bytes, filename: str) -> dict:
    """บันทึก reference image + สร้าง thumbnail — คืน dict ของ path ทั้งคู่.

    ค่า `content` ถูกตรวจขนาดก่อน Pillow จะเปิด — กัน memory blowup จากไฟล์ยักษ์.
    """
    ext = _ext(filename)
    if ext not in ALLOWED_EXT:
        raise ValidationError("ไฟล์ต้องเป็น PNG/JPEG/WebP")

    max_bytes = settings.MEDIA_MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise PayloadTooLargeError(f"ไฟล์เกิน {settings.MEDIA_MAX_UPLOAD_MB} MB")

    from PIL import Image
    import io

    try:
        img = Image.open(io.BytesIO(content))
        img.verify()
    except Exception as e:  # noqa: BLE001
        raise ValidationError(f"ไฟล์รูปไม่ถูกต้อง: {e}")

    img = Image.open(io.BytesIO(content))
    if max(img.size) > settings.MEDIA_MAX_DIMENSION:
        raise ValidationError(f"รูปใหญ่เกิน {settings.MEDIA_MAX_DIMENSION}px")

    ref_path = _safe_path(stunt_id, f"reference.{ext}")
    os.makedirs(os.path.dirname(ref_path), exist_ok=True)
    _atomic_write(ref_path, content)

    # thumbnail (WebP, max 480, RGB — กัน EXIF orientation/alpha ผิด)
    thumb_path = _safe_path(stunt_id, "thumb.webp")
    img = img.convert("RGB")
    img.thumbnail((settings.MEDIA_THUMB_DIMENSION, settings.MEDIA_THUMB_DIMENSION))
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=80)
    _atomic_write(thumb_path, buf.getvalue())

    # คืน relative path (ไม่ absolute) — เก็บใน DB ให้ย้าย media root ได้
    return {
        "reference_image_path": _relative(ref_path),
        "thumbnail_path": _relative(thumb_path),
    }


def _atomic_write(path: str, content: bytes) -> None:
    tmp = path + f".{uuid.uuid4().hex}.tmp"
    with open(tmp, "wb") as f:
        f.write(content)
    os.replace(tmp, path)


def _relative(path: str) -> str:
    return os.path.relpath(path, _root())


def resolve_relative(rel_path: str) -> str:
    """แปลง relative path ที่เก็บใน DB เป็น absolute — กัน traversal."""
    if not rel_path:
        raise ValidationError("ไม่มี path ของไฟล์")
    return _safe_path_from_rel(rel_path)


def _safe_path_from_rel(rel_path: str) -> str:
    root = _root()
    path = os.path.abspath(os.path.join(root, rel_path))
    if not path.startswith(root + os.sep):
        raise ValidationError("path ออกจาก media root")
    return path


# ── signed URL (HMAC) ───────────────────────────────────────────────
# ทำไมต้องมี: `<img src="...">` แนบ `Authorization: Bearer` ไม่ได้ ⇒ ถ้าใช้ endpoint
# ที่ต้อง auth ภาพจะโหลดไม่ขึ้นในเบราว์เซอร์ · การแนบ JWT ไปใน query ก็เสี่ยงหลุดใน log
# ⇒ ใช้โทเคนสั้นที่ลงนามด้วย SECRET_KEY และผูกกับ path + เวลาหมดอายุ

def _signature(rel_path: str, expires_at: int) -> str:
    msg = f"{rel_path}\n{expires_at}".encode()
    digest = hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def signed_url(rel_path: str | None, ttl: int | None = None) -> str | None:
    """สร้าง URL สำหรับ `<img>` — คืน None ถ้าไม่มีไฟล์."""
    if not rel_path:
        return None
    expires_at = int(time.time()) + (ttl or settings.MEDIA_SIGNED_TTL_SECONDS)
    sig = _signature(rel_path, expires_at)
    return (
        f"/api/v1/media/{quote(rel_path, safe='/')}"
        f"?exp={expires_at}&sig={quote(sig)}"
    )


def verify_signed_path(rel_path: str, expires_at: int, sig: str) -> str:
    """ตรวจ signature + อายุ แล้วคืน absolute path (raise ValidationError ถ้าไม่ผ่าน)."""
    if not rel_path or not sig:
        raise ValidationError("ลิงก์ไฟล์ไม่ครบ")
    if expires_at < int(time.time()):
        raise ValidationError("ลิงก์ไฟล์หมดอายุ")
    expected = _signature(rel_path, int(expires_at))
    if not hmac.compare_digest(expected, sig):
        raise ValidationError("ลายเซ็นไฟล์ไม่ถูกต้อง")
    return resolve_relative(rel_path)


def delete_stunt_files(stunt_id: int) -> None:
    """ลบไฟล์ reference/thumb ของ stunt (best-effort)."""
    import shutil
    d = os.path.dirname(_safe_path(stunt_id, "x"))
    shutil.rmtree(d, ignore_errors=True)
