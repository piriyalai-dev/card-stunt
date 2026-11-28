# Testing Rules (card-stunt)

## Backend

- pytest + pytest-asyncio · test harness `docker compose -f docker-compose.test.yml run --rm test_runner`
- `test_db_url` สร้าง DB สุ่มชื่อต่อ session → `init_db` → drop ตอนจบ · `clean_database` TRUNCATE ก่อนทุก test
- 2 สไตล์: HTTP end-to-end (`client` + `TestClient`) และ service-level (`db_pool`)

## หลัก (Deep verification)

- **ห้าม** assert แค่ `status_code == 200` — ตรวจ state จริงใน DB (`db_pool`) ด้วย query อิสระ
- soft delete → assert `deleted_at IS NOT NULL` (ไม่ใช่ "แถวหาย")
- ห้าม hardcode id · สร้าง "โลกทดสอบ" ใน fixture แล้วคืน id/token ออกมา

## Mock

- **mock เฉพาะขอบที่ออกนอก process** (enqueue งานเบื้องหลัง, push จริง) — `require_permission` ใช้ user จริง
  (ได้ทดสอบ RBAC ไปด้วย)
- ไม่ mock เวลา — ใช้ `datetime.now() ± timedelta(days=1)` (หน่วยวัน ไม่ใช่วินาที กัน flaky)

## Edge case

- validation/boundary → `@pytest.mark.parametrize`
- แยก 400 (service `ValidationError`) vs 422 (Pydantic) — เขียน `== 422` ตัวเดียวจะพลาดครึ่งด่าน

## Frontend

- vitest (`npm run test:unit`) · ไฟล์ใน `src/__tests__/*.spec.ts`
- `npm run type-check` (vue-tsc) + `npm run lint` (oxlint + eslint) + `npm run build`

## Logging ลง skills.md (บังคับ)

- เจอบั๊ก/รูปแบบไม่ชัด → บันทึกลง `docs/skills.md` เป็น entry `### 🛠️` **ทันที** (ก่อน/หลัง fix)
- หัวข้อบอก **อาการ** ไม่ใช่ชื่อโมดูล · ก่อนเขียน grep หัวข้อเดิมก่อน (แก้ entry เดิม ไม่เพิ่มอันซ้ำ)

## หลัก

- ห้าม hardcode id · เทสต์ต้องเดาได้ว่าค่าคืออะไร
- เทสต์ coordinate/direction/RBAC เป็นหัวใจของระบบแปรอักษร (Phase 3+)
