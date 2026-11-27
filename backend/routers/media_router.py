"""🖼️ Media serving — signed URL (ไม่ต้อง Bearer token เพื่อให้ `<img src>` ใช้ได้)."""
import mimetypes
import os

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from core import media
from core.exceptions import ValidationError

router = APIRouter(prefix="/media", tags=["Media"])


@router.get("/{path:path}", name="get_media")
async def get_media(path: str, exp: int = Query(...), sig: str = Query(...)):
    try:
        absolute = media.verify_signed_path(path, exp, sig)
    except ValidationError as e:
        # 403 ไม่ใช่ 404 — ให้แยก "ลายเซ็นผิด/หมดอายุ" ออกจาก "ไฟล์ไม่มี" ได้
        raise HTTPException(status_code=403, detail=str(e))

    if not os.path.isfile(absolute):
        raise HTTPException(status_code=404, detail="ไม่พบไฟล์")

    media_type = mimetypes.guess_type(absolute)[0] or "application/octet-stream"
    return FileResponse(
        absolute,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=600"},
    )
