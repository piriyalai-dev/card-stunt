"""
ชื่อ ARQ queue — แหล่งความจริงเดียวของทั้งสองฝั่ง (ผู้ส่ง + ผู้รับ)

Phase 3 ยังไม่มี worker — ไฟล์นี้ประกาศชื่อคิว export ไว้ล่วงหน้าให้ ARQ worker
(Phase 5) กับ `services/exports_service` อ้างค่าตัวเดียวกัน ไม่ drift กัน
(หลักเดียวกับ prsc_portal/core/queues.py)
"""

# คิวงาน export PDF/CSV/ZIP — worker ตั้ง max_jobs=1 (เขียนไฟล์ชนกันได้)
EXPORT_QUEUE = "pixelstand:queue:export"
