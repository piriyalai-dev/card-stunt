#!/usr/bin/env bash
# =============================================================================
# restore.sh — ซ้อมกู้คืน (restore drill) บน scratch DB + scratch media
# ⚠️ ไม่แตะ DB/volume จริง — สร้าง <db>_drill_<ts> แล้วลบเอง
#
#   ops/backup/restore.sh --dump ~/backups/pixelstand/db/db-….dump [--media …tgz]
# =============================================================================
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)
cd "$REPO_DIR"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
die() { log "❌ $*"; exit 1; }

usage() { echo "ใช้: ops/backup/restore.sh --dump <file.dump> [--media <file.tgz>] [--keep]"; exit 2; }

DUMP=""; MEDIA=""; KEEP=0
while [ $# -gt 0 ]; do
    case "$1" in
        --dump) DUMP="${2:-}"; shift 2 ;;
        --media) MEDIA="${2:-}"; shift 2 ;;
        --keep) KEEP=1; shift ;;
        -h|--help) usage ;;
        *) die "ไม่รู้จัก argument: $1" ;;
    esac
done
[ -n "$DUMP" ] || usage
[ -f "$DUMP" ] || die "ไม่พบ dump: $DUMP"

[ -f .env ] || die "ไม่พบ .env"
set -a; . ./.env; set +a
: "${POSTGRES_USER:?}"; : "${POSTGRES_PASSWORD:?}"; : "${POSTGRES_DB:?}"

DB_CID=$(docker ps -q -f "name=^pixelstand_infra_db([.]|$)" | head -n1)
[ -n "$DB_CID" ] || die "ไม่พบ container pixelstand_infra_db"

TS=$(date +%H%M%S)
SCRATCH="${POSTGRES_DB}_drill_${TS}"
log "🐘 สร้าง scratch DB $SCRATCH"
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$DB_CID" createdb -U "$POSTGRES_USER" "$SCRATCH"
cleanup() { docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$DB_CID" dropdb -U "$POSTGRES_USER" "$SCRATCH" --if-exists 2>/dev/null || true; }
trap cleanup EXIT

log "🐘 pg_restore"
docker exec -i -e PGPASSWORD="$POSTGRES_PASSWORD" "$DB_CID" \
    pg_restore -U "$POSTGRES_USER" -d "$SCRATCH" --exit-on-error < "$DUMP" || die "pg_restore ล้ม"

if [ -n "$MEDIA" ]; then
    [ -f "$MEDIA" ] || die "ไม่พบ media: $MEDIA"
    TMPD=$(mktemp -d /tmp/pixelstand-restore-XXXX)
    log "🖼️ แตก media ลง $TMPD"
    tar -xzf "$MEDIA" -C "$TMPD"
    log "🔍 verify_media.py (DB scratch + media ที่แตก)"
    BACKEND_IMAGE=$(docker inspect -f '{{.Config.Image}}' "$(docker ps -q -f name=^pixelstand_app_backend | head -n1)")
    docker run --rm --network container:"$DB_CID" \
        -e "DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${SCRATCH}" \
        -e "API_KEY=${API_KEY:-}" -e "SECRET_KEY=${SECRET_KEY:-}" -e "JWT_SECRET=${JWT_SECRET:-}" \
        -v "$TMPD":/media "$BACKEND_IMAGE" python scripts/verify_media.py --media-dir /media \
        || { log "❌ verify ไม่ผ่าน — ตรวจ dump/media ว่ามาจากเวลาเดียวกัน"; [ "$KEEP" = "1" ] || rm -rf "$TMPD"; exit 1; }
    [ "$KEEP" = "1" ] || rm -rf "$TMPD"
fi

log "🟢 restore drill ผ่าน — scratch ถูกลบแล้ว"
