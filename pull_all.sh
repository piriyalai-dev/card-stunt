#!/usr/bin/env bash
# Pixel Stand — ดึงโค้ดล่าสุด + build + deploy (Swarm, zero-downtime)
# โครงสร้างตาม pirivoice (prsc_portal/pull_all.sh) + safety จาก classroom-management
#
# ⚠️ set -euo pipefail — ถ้า build/deploy ล้ม ต้องหยุดทันที ไม่ deploy เงียบ ๆ ผิด
# ⚠️ `git reset --hard` ทิ้ง local change — อย่ารันบน working tree สกปรก
set -euo pipefail

cd "$(dirname "$0")"

# 1. โหลด .env
if [ -f .env ]; then
    set -a; . ./.env; set +a
else
    echo "❌ ไม่พบ .env — รัน ./setup.sh ก่อน"; exit 1
fi

CURRENT_BRANCH=$(git branch --show-current)
if [ -z "$CURRENT_BRANCH" ]; then
    echo "❌ ไม่สามารถหาชื่อ branch ได้"; exit 1
fi

# 2. ดึงโค้ดล่าสุด
echo "⬇️ กำลังดึงโค้ดล่าสุด..."
git fetch origin
git reset --hard "origin/$CURRENT_BRANCH"

# 3. Git LFS (เฉพาะเมื่อ repo ใช้ LFS — ปัจจุบัน card-stunt ไม่มีไฟล์ LFS)
if grep -q 'filter=lfs' .gitattributes 2>/dev/null || [ -n "$(git lfs ls-files 2>/dev/null)" ]; then
    echo "📦 กำลังดึง Git LFS..."
    git lfs pull || { echo "❌ git lfs pull ล้มเหลว"; exit 1; }
else
    echo "ℹ️ ไม่มีไฟล์ Git LFS — ข้าม"
fi

# 4. image tag = commit สั้น
export IMAGE_TAG=$(git rev-parse --short HEAD)
echo "🏷️ Commit: ${IMAGE_TAG}"

# 5. Build (host network — container บนเครื่องนี้ resolve DNS ไม่ได้ 2026-11-25)
BUILD_NETWORK="--network=${DOCKER_BUILD_NETWORK:-host}"
echo "🔨 Build backend (GIT_SHA=${IMAGE_TAG})..."
docker build $BUILD_NETWORK --build-arg GIT_SHA="${IMAGE_TAG}" -t "pixelstand-backend:${IMAGE_TAG}" ./backend
echo "🔨 Build frontend (VITE_API_BASE_URL=${VITE_API_BASE_URL:-http://localhost:8000})..."
docker build $BUILD_NETWORK --build-arg VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://localhost:8000}" -t "pixelstand-frontend:${IMAGE_TAG}" ./frontend

# 6. ตรวจ image มีจริงก่อน deploy (docker stack deploy ไม่ตรวจให้)
for img in pixelstand-backend pixelstand-frontend; do
    if ! docker image inspect "${img}:${IMAGE_TAG}" >/dev/null 2>&1; then
        echo "❌ ไม่พบ image ${img}:${IMAGE_TAG} — หยุดก่อน deploy"; exit 1
    fi
done
echo "✅ image ครบพร้อม deploy"

# 7. Deploy (zero-downtime)
echo "🚀 Deploy stack pixelstand_app..."
docker stack deploy -c docker-compose.app.yml pixelstand_app

# 8. รอ service ขึ้นครบ + rollover จบ (กัน "สำเร็จ" แต่ task ใหม่ขึ้นไม่ได้)
service_update_state() {
    docker service inspect "$1" --format '{{if .UpdateStatus}}{{.UpdateStatus.State}}{{else}}none{{end}}'
}

DEPLOY_WAIT_SECONDS="${DEPLOY_WAIT_SECONDS:-300}"
echo "⏳ รอ service ขึ้นครบและ rollover จบ (สูงสุด ${DEPLOY_WAIT_SECONDS}s)..."
deadline=$((SECONDS + DEPLOY_WAIT_SECONDS))
ready_streak=0
while :; do
    not_ready=""
    services_out=$(docker stack services pixelstand_app --format '{{.Name}} {{.Replicas}}')
    while read -r name replicas; do
        [ -z "$name" ] && continue
        if [ -z "$replicas" ] || [ "${replicas%%/*}" != "${replicas##*/}" ]; then
            not_ready+="  ${name} replicas=${replicas}"$'\n'
        fi
        state=$(service_update_state "$name")
        case "$state" in
            none|completed) ;;
            paused|rollback_started|rollback_paused|rollback_completed)
                echo "❌ swarm หยุด/ย้อนการอัปเดต ${name} (UpdateStatus=${state})"
                echo "   ตรวจ: docker service ps ${name} --no-trunc"
                exit 1 ;;
            *) not_ready+="  ${name} update=${state}"$'\n' ;;
        esac
    done <<< "$services_out"

    if [ -z "$not_ready" ]; then
        ready_streak=$((ready_streak + 1))
        if [ "$ready_streak" -ge 2 ]; then
            echo "✅ ทุก service ขึ้นครบตาม spec และ rollover จบแล้ว"; break
        fi
        sleep 5; continue
    fi
    ready_streak=0
    if [ "$SECONDS" -ge "$deadline" ]; then
        echo "❌ service ไม่ขึ้นครบภายใน ${DEPLOY_WAIT_SECONDS}s:"; printf '%s' "$not_ready"
        echo "   ตรวจ: docker service ps <service> --no-trunc"; exit 1
    fi
    sleep 5
done

echo "✅ อัปเดตเสร็จสมบูรณ์ (IMAGE_TAG=${IMAGE_TAG}) ระบบทำงานต่อเนื่องไม่มีสะดุด!"
