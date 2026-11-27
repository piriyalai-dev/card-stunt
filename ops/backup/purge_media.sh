#!/usr/bin/env bash
# =============================================================================
# purge_media.sh — wrapper ให้ cron เรียก purge_media.py บน backend image
#   ops/backup/purge_media.sh             # dry-run
#   ops/backup/purge_media.sh --apply     # ลบจริง (cron ใช้ตัวนี้)
# =============================================================================
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)
cd "$REPO_DIR"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
die() { log "❌ $*"; exit 1; }

[ -f .env ] || die "ไม่พบไฟล์ .env ที่ $REPO_DIR"
set -a; . ./.env; set +a
: "${POSTGRES_USER:?POSTGRES_USER ไม่มีใน .env}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD ไม่มีใน .env}"
: "${POSTGRES_DB:?POSTGRES_DB ไม่มีใน .env}"

BACKEND_CID=$(docker ps -q -f "name=^pixelstand_app_backend([.]|$)" | head -n1)
[ -n "$BACKEND_CID" ] || die "ไม่พบ backend container pixelstand_app_backend ที่รันอยู่"
BACKEND_IMAGE=$(docker inspect -f '{{.Config.Image}}' "$BACKEND_CID")

log "🧹 purge_media ด้วย image $BACKEND_IMAGE"
exec docker run --rm --network container:"$BACKEND_CID" \
    -e "DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@pixelstand_infra_db:5432/${POSTGRES_DB}" \
    -e MEDIA_STORAGE_DIR=/data/media \
    -e "API_KEY=${API_KEY:-}" -e "SECRET_KEY=${SECRET_KEY:-}" -e "JWT_SECRET=${JWT_SECRET:-}" \
    -v "pixelstand_media_data":/data/media \
    "$BACKEND_IMAGE" python scripts/purge_media.py "$@"
