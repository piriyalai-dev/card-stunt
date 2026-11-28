#!/usr/bin/env bash
# Pixel Stand — bootstrap แบบปุ่มเดียวจบ (One-Shot Boot) · single environment
# (ดัดแปลงจาก pirivoice setup.sh — ไม่มี ENV_NAME ใช้ชื่อคงที่ pixelstand)
#
#   ./setup.sh              # ทำทุกอย่าง
#   ./setup.sh --no-build   # ข้าม build ใช้ image ที่มีอยู่
#   ./setup.sh --help
set -euo pipefail

cd "$(dirname "$0")"

red()    { printf "\033[1;31m%s\033[0m\n" "$*"; }
green()  { printf "\033[1;32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[1;33m%s\033[0m\n" "$*"; }
cyan()   { printf "\033[1;36m%s\033[0m\n" "$*"; }
step()   { echo; cyan "▶ $*"; }

usage() { awk 'NR>=3 && /^#/ { gsub(/^# ?/, ""); print }' "$0"; exit 0; }

NO_BUILD=0
for arg in "$@"; do
    case "$arg" in
        --no-build) NO_BUILD=1 ;;
        -h|--help)  usage ;;
        *)          yellow "⚠️ ไม่รู้จักตัวเลือก: $arg" ;;
    esac
done

STACK_INFRA="pixelstand_infra"
STACK_APP="pixelstand_app"
NET="pixelstand-internal"
BACKEND_IMG="pixelstand-backend"
FRONTEND_IMG="pixelstand-frontend"

step "โหลด .env"
if [ ! -f .env ]; then
    red "❌ ไม่พบ .env — คัดลอกก่อน: cp .env.example .env แล้วแก้ค่า"
    exit 1
fi
set -a; . ./.env; set +a

for v in API_DOMAIN WEB_DOMAIN POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB API_KEY SECRET_KEY JWT_SECRET VITE_API_BASE_URL; do
    if [ -z "${!v:-}" ]; then red "❌ ยังไม่ได้ตั้ง $v ใน .env"; exit 1; fi
done
green "   ✔ โหลด .env แล้ว"

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
    red "❌ Docker daemon ไม่ทำงาน"; exit 1
fi

step "1/5 ตรวจสอบ Docker Swarm"
if docker node ls >/dev/null 2>&1; then green "   ✔ Swarm เปิดอยู่แล้ว"
else docker swarm init; green "   ✔ Swarm พร้อมใช้แล้ว"; fi

step "2/5 สร้าง Docker Networks"
for net in "$NET" "traefik-public"; do
    if docker network ls --format '{{.Name}}' | grep -qx "$net"; then
        green "   ✔ Network $net มีอยู่แล้ว"
    else
        docker network create --driver=overlay "$net"; green "   ✔ สร้าง $net"
    fi
done

step "3/5 ตรวจ Traefik Proxy (แชร์ตัวกลาง 1 เครื่อง 1 อัน)"
if docker ps --format '{{.Image}}' | grep -qiE '(^|/)traefik[:@]'; then
    green "   ✔ พบ Traefik — ใช้ตัวกลางร่วม"
else
    yellow "   ⚠️ ยังไม่พบ Traefik — ติดตั้งครั้งเดียวต่อเครื่อง: ./setup_traefik.sh"
fi

step "สร้าง Docker Secrets (idempotent — credential ออกจาก env)"
ensure_secret() {
    local name="$1" var="$2"
    if docker secret inspect "$name" >/dev/null 2>&1; then
        green "   ✔ Secret $name มีอยู่แล้ว"
    else
        printf '%s' "${!var}" | docker secret create "$name" -
        green "   ✔ สร้าง secret $name (จาก \$$var)"
    fi
}
ensure_secret pixelstand_postgres_password POSTGRES_PASSWORD
ensure_secret pixelstand_api_key API_KEY
ensure_secret pixelstand_secret_key SECRET_KEY
ensure_secret pixelstand_jwt_secret JWT_SECRET

step "4/5 Deploy Infrastructure (PostgreSQL + Redis)"
docker stack deploy -c docker-compose.infra.yml "$STACK_INFRA"
green "   ✔ Stack $STACK_INFRA ถูก deploy แล้ว"

wait_service() {
    local svc="$1" timeout="${2:-60}"
    for _ in $(seq 1 "$timeout"); do
        if docker service ps "$svc" --format '{{.CurrentState}}' 2>/dev/null | grep -q '^Running'; then
            green "   ✔ $svc ทำงานแล้ว"; return 0
        fi
        sleep 2
    done
    yellow "   ⚠️ ยังไม่เห็น $svc — ลอง deploy app ต่อ (healthcheck คอยรอ db เอง)"
}
wait_service "${STACK_INFRA}_db" 60
wait_service "${STACK_INFRA}_redis" 30

step "5/5 Build Images + Deploy App"
if [ -z "${IMAGE_TAG:-}" ]; then
    IMAGE_TAG=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")
fi
export IMAGE_TAG
echo "   🏷️ Image tag: $IMAGE_TAG"

BUILD_NETWORK="--network=${DOCKER_BUILD_NETWORK:-host}"
if [ "$NO_BUILD" = "1" ]; then
    yellow "   ⏭️ (--no-build) ใช้ image ${BACKEND_IMG}:${IMAGE_TAG} / ${FRONTEND_IMG}:${IMAGE_TAG}"
else
    docker build $BUILD_NETWORK --build-arg GIT_SHA="${IMAGE_TAG}" -t "${BACKEND_IMG}:${IMAGE_TAG}" ./backend
    docker build $BUILD_NETWORK --build-arg VITE_API_BASE_URL="${VITE_API_BASE_URL}" -t "${FRONTEND_IMG}:${IMAGE_TAG}" ./frontend
    green "   ✔ Build เสร็จทั้ง 2 image"
fi

docker stack deploy -c docker-compose.app.yml "$STACK_APP"
green "   ✔ Stack $STACK_APP ถูก deploy แล้ว"

echo
green "✅ ============================================================"
green "✅ Pixel Stand พร้อมใช้งานแล้ว!"
green "✅ ============================================================"
echo
echo "   🌐 Web:  ${WEB_DOMAIN}"
echo "   🔌 API:  ${API_DOMAIN}"
echo "   🐘 Infra: stack $STACK_INFRA (PostgreSQL + Redis)"
echo "   📦 App:   stack $STACK_APP (backend + frontend)"
echo
echo "   ตรวจสถานะ: docker stack ps $STACK_APP"
echo "   ดู log:    docker service logs -f ${STACK_APP}_backend"
echo
echo "   📌 ครั้งถัดไป:"
echo "      อัปเดตโค้ดใหม่    → ./pull_all.sh"
echo "      Rollback ฉุกเฉิน  → ./rollback.sh <tag>"
