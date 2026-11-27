#!/usr/bin/env bash
# 🛡️ setup_traefik.sh — ติดตั้ง Traefik Proxy ตัวกลาง (1 เครื่อง 1 อัน)
#
# ⚠️ card-stunt **แชร์** global_proxy ที่มีอยู่บนเครื่องนี้แล้ว — สคริปต์นี้ปลอดภัย
#    ถ้าพบ Traefik รันอยู่แล้ว จะไม่ deploy/แตะอะไร (exit 0)
#
#   ./setup_traefik.sh            # ติดตั้ง / ตรวจสอบ (idempotent)
#   ./setup_traefik.sh --remove   # ถอด Traefik (docker stack rm global_proxy)
set -euo pipefail

cd "$(dirname "$0")"

red()    { printf "\033[1;31m%s\033[0m\n" "$*"; }
green()  { printf "\033[1;32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[1;33m%s\033[0m\n" "$*"; }
cyan()   { printf "\033[1;36m%s\033[0m\n" "$*"; }
step()   { echo; cyan "▶ $*"; }

usage() { awk 'NR>=3 && /^#/ { gsub(/^# ?/, ""); print }' "$0"; exit 0; }

REMOVE=0
for arg in "$@"; do
    case "$arg" in
        --remove)  REMOVE=1 ;;
        -h|--help) usage ;;
        *)         yellow "⚠️ ไม่รู้จักตัวเลือก: $arg" ;;
    esac
done

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
    red "❌ Docker daemon ไม่ทำงาน"; exit 1
fi

if [ "$REMOVE" = "1" ]; then
    step "ถอด Traefik ออกจากเครื่อง"
    docker stack rm global_proxy || true
    green "   ✔ ถอด global_proxy แล้ว (network traefik-public คงไว้)"
    exit 0
fi

# ถ้า Traefik รันอยู่แล้ว (ของเครื่องนี้ / ระบบอื่น) → อย่าแตะ
if docker ps --format '{{.Image}}' | grep -qiE '(^|/)traefik[:@]'; then
    green "✔ พบ Traefik Proxy รันอยู่แล้ว — ใช้ตัวกลางร่วม ไม่ต้องติดตั้งใหม่"
    exit 0
fi

step "1/3 เปิด Docker Swarm"
if docker node ls >/dev/null 2>&1; then green "   ✔ Swarm เปิดอยู่แล้ว"
else docker swarm init; green "   ✔ Swarm พร้อมใช้แล้ว"; fi

step "2/3 สร้าง Network traefik-public"
if docker network ls --format '{{.Name}}' | grep -qx "traefik-public"; then green "   ✔ มีอยู่แล้ว"
else docker network create --driver=overlay traefik-public; green "   ✔ สร้างแล้ว"; fi

step "3/3 Deploy Traefik (stack global_proxy · port 80)"
docker stack deploy -c docker-compose.proxy.yml global_proxy
green "   ✔ Traefik พร้อมใช้งานแล้ว"
