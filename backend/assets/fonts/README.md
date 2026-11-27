# Fonts

| ไฟล์ | ใช้ทำอะไร | license |
|---|---|---|
| `NotoSansThai.ttf` | วาดข้อความไทยใน PDF export (Pillow + Raqm shaping) | SIL Open Font License 1.1 — © Google LLC |

ไฟล์นี้ถูกคัดลอกมาจาก `~/.local/share/fonts/NotoSansThai.ttf` ของเครื่อง dev
เพื่อให้ Docker image มีฟอนต์เดียวกับที่ใช้ทดสอบ · ห้ามลบ — `services/export_builders.py`
จะ fallback ไป DejaVu (ไม่มีสระ/วรรณยุกต์ไทยครบ) ถ้าไม่พบไฟล์นี้
