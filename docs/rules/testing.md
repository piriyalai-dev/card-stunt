# Testing Rules (card-stunt)

## Backend

- pytest + pytest-asyncio · test harness `docker compose -f docker-compose.test.yml run --rm test_runner`
- `test_db_url` สร้าง DB สุ่มชื่อต่อ session → `init_db` → drop ตอนจบ · `clean_database` TRUNCATE ก่อนทุก test
- 2 สไตล์: HTTP end-to-end (`client` + `TestClient`) และ service-level (`db_pool`)

## Frontend

- vitest (`npm run test:unit`) · ไฟล์ใน `src/__tests__/*.spec.ts`
- `npm run type-check` (vue-tsc) + `npm run lint` (oxlint + eslint) + `npm run build`

## หลัก

- ห้าม hardcode id · เทสต์ต้องเดาได้ว่าค่าคืออะไร
- เทสต์ coordinate/direction/RBAC เป็นหัวใจของระบบแปรอักษร (Phase 3+)
