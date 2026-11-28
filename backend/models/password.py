"""นโยบายความแข็งแรงของรหัสผ่าน — แหล่งความจริงเดียว (ใช้ใน auth + users schemas).

ใช้ผ่าน Pydantic `field_validator`: `_v = field_validator("new_password")(validate_password_strength)`
ฟังก์ชันนี้ต้อง raise `ValueError` (ไม่ใช่ domain exception) เพื่อให้ Pydantic แปลงเป็น 422 ถูกต้อง
"""
from typing import Optional


def validate_password_strength(v: Optional[str]) -> Optional[str]:
    """รหัสผ่านต้อง ≥8 ตัวอักษร และมีทั้งตัวอักษรกับตัวเลข. คืน v ตรง ๆ (None ผ่าน — สำหรับ field optional)."""
    if v is None:
        return v
    if len(v) < 8:
        raise ValueError("รหัสผ่านต้องยาวอย่างน้อย 8 ตัวอักษร")
    if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
        raise ValueError("รหัสผ่านต้องมีทั้งตัวอักษรและตัวเลข")
    return v
