#!/usr/bin/env bash
#
# rollback.sh — สลับ stack กลับไป image ชุดก่อน โดยไม่แตะ git เลย
#
#   ./rollback.sh --list                 # ดู image tag ที่มี (ใหม่ → เก่า)
#   ./rollback.sh <image-tag> --dry-run  # ตรวจว่า image มีจริง จะสลับอะไรบ้าง
#   ./rollback.sh <image-tag>            # สลับจริง (ถามยืนยัน)
#   ./rollback.sh <image-tag> --yes      # สลับจริงไม่ถาม (ใช้ใน automate)
#
# <image-tag> = commit hash ที่ใช้ tag image ตอน deploy · ไม่แก้ git
set -euo pipefail

cd "$(dirname "$0")"

TAG=""
DRY_RUN=0
ASSUME_YES=0
LIST=0

die() { echo "❌ $*" >&2; exit 1; }
ok()  { echo "✅ $*"; }
step() { echo; echo "▶ $*"; }

usage() { awk 'NR >= 2 && /^#/ { sub(/^# ?/, ""); print; next } NR >= 2 { exit }' "$0"; exit 0; }

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        --yes|-y)  ASSUME_YES=1; shift ;;
        --list)    LIST=1; shift ;;
        -h|--help) usage ;;
        -*)        die "ไม่รู้จักตัวเลือก: $1" ;;
        *)         [ -z "$TAG" ] || die "ระบุ image tag ได้ครั้งเดียว"; TAG="$1"; shift ;;
    esac
done

command -v docker >/dev/null 2>&1 || die "ไม่พบ docker"

BACKEND_IMAGE="pixelstand-backend"
FRONTEND_IMAGE="pixelstand-frontend"
STACK="pixelstand_app"

if [ "$LIST" = "1" ]; then
    step "image tag ที่มีในเครื่อง"
    for img in "$BACKEND_IMAGE" "$FRONTEND_IMAGE"; do
        echo "$img:"
        docker image ls "$img" --format '  {{.Tag}}\t{{.CreatedAt}}' | grep -v '^  <none>' | sort -k2,3 -r | head -15
    done
    echo; echo "ใช้: ./rollback.sh <tag> --dry-run"
    exit 0
fi

[ -n "$TAG" ] || die "ใช้: ./rollback.sh <image-tag> [--dry-run|--yes]  หรือ ./rollback.sh --list"
[[ "$TAG" =~ ^[0-9a-f]{7,40}$ ]] || die "image tag ต้องเป็น commit hash 7–40 ตัว (พบ: $TAG)"

step "ตรวจ image $TAG"
for img in "$BACKEND_IMAGE" "$FRONTEND_IMAGE"; do
    docker image inspect "$img:$TAG" >/dev/null 2>&1 || die "ไม่พบ image $img:$TAG (ดูรายการด้วย ./rollback.sh --list)"
    ok "$img:$TAG"
done

current_image() {
    docker service inspect "${STACK}_$1" --format '{{.Spec.TaskTemplate.ContainerSpec.Image}}' 2>/dev/null || echo "(ไม่พบ service)"
}

step "จะสลับ stack ${STACK}"
echo "  backend  : $(current_image backend)"
echo "          → ${BACKEND_IMAGE}:${TAG}"
echo "  frontend : $(current_image frontend)"
echo "          → ${FRONTEND_IMAGE}:${TAG}"

if [ "$DRY_RUN" = "1" ]; then
    echo; ok "dry-run — image มีครบ ไม่ได้ deploy อะไร"; exit 0
fi

echo
echo "⚠️ หลังสลับ checkout git จะอยู่ที่เดิม (รัน pull_all.sh ครั้งถัดไปจะ deploy HEAD กลับมา)"
if [ "$ASSUME_YES" = "0" ]; then
    read -r -p "พิมพ์ 'rollback' เพื่อยืนยัน: " ans
    [ "$ans" = "rollback" ] || die "ยกเลิก — ไม่ได้แตะอะไร"
fi

step "deploy ${STACK} ด้วย IMAGE_TAG=$TAG"
export IMAGE_TAG="$TAG"
docker stack deploy -c docker-compose.app.yml "$STACK"

step "ตรวจหลัง deploy"
for svc in backend frontend; do
    running="$(current_image "$svc")"
    if [[ "$running" == *":$TAG"* ]]; then
        ok "$svc → $running"
    else
        echo "  ? $svc → ${running:-ไม่พบ service}"
    fi
done

ok "rollback ไป $TAG เสร็จ — ถ้าจะกลับเวอร์ชันล่าสุด รัน ./pull_all.sh"
