#!/usr/bin/env bash
# Pixel Stand — bootstrap (Phase 2: local + test first)
# ⚠️ ยังไม่ deploy ลง Swarm — `docker stack deploy` มาใน Phase 5
set -euo pipefail

cd "$(dirname "$0")"

echo "== Pixel Stand setup =="

if [ ! -f .env ]; then
  echo "📄 ไม่พบ .env — สร้างจาก .env.example"
  cp .env.example .env
  echo "⚠️ แก้ค่าใน .env (POSTGRES_PASSWORD / API_KEY / SECRET_KEY / JWT_SECRET) แล้วรันใหม่"
  exit 1
fi

# 1. ตรวจ syntax ของ compose (ไม่ deploy)
docker compose -f docker-compose.infra.yml config > /dev/null && echo "✅ infra.yml syntax OK"
docker compose -f docker-compose.app.yml config > /dev/null && echo "✅ app.yml syntax OK"

# 2. smoke test ฝั่ง backend (test harness: Postgres จริง + pytest)
echo "🧪 รัน backend tests..."
docker compose -f docker-compose.test.yml run --rm test_runner

# 3. คำสั่งถัดไป (พิมพ์ให้ผู้ใช้)
cat <<'EOF'

✅ Phase 2 smoke test ผ่าน
ขั้นถัดไป (Phase 3+):
  - รัน backend หลังบ้าน local:  cd backend && pip install -r requirements.txt && uvicorn main:app --reload
  - รัน frontend dev:            cd frontend && npm install && npm run dev
  - Deploy ลง Swarm (Phase 5):
      docker network create -d overlay --attachable pixelstand-internal
      docker stack deploy -c docker-compose.infra.yml pixelstand_infra
      IMAGE_TAG=<sha> docker stack deploy -c docker-compose.app.yml pixelstand_app
EOF
