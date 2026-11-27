#!/usr/bin/env bash
# Pixel Stand — ดึงโค้ดล่าสุด + build ใหม่ (โหมด local)
# ⚠️ Swarm deploy (`docker stack deploy`) มาใน Phase 5 — ตอนนี้เป็น local compose
set -euo pipefail

cd "$(dirname "$0")"

[ -f .env ] || { echo "❌ ไม่พบ .env — รัน ./setup.sh ก่อน"; exit 1; }
set -a; . ./.env; set +a

git fetch origin && git reset --hard "origin/$(git branch --show-current)"

export IMAGE_TAG="$(git rev-parse --short HEAD)"
docker compose -f docker-compose.app.yml build
docker compose -f docker-compose.app.yml up -d

echo "✅ build + รันสำเร็จ (IMAGE_TAG=$IMAGE_TAG)"
