#!/usr/bin/env bash
# =============================================================================
# backup.sh — สำรอง DB (pg_dump) + รูป (media volume) ของ Pixel Stand
# (ดัดแปลงจาก pirivoice ops/backup/backup.sh — single env, ชื่อ pixelstand)
#
# ใช้:  ops/backup/backup.sh
# env ที่อ่านจาก .env: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
# env ที่ปรับได้: BACKUP_ROOT=$HOME/backups/pixelstand · DB_RETENTION_DAYS=30
#                RCLONE_CONFIG · RCLONE_REMOTE=gdrive · RCLONE_DEST=PixelStandBackup
#
# exit: 0 = สำเร็จ (รวม "ยังไม่มี rclone config") · 1 = local backup ล้ม · 3 = offsite ล้ม
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

BACKUP_ROOT="${BACKUP_ROOT:-$HOME/backups/pixelstand}"
DB_DIR="$BACKUP_ROOT/db"
MEDIA_DIR="$BACKUP_ROOT/media"
DB_RETENTION_DAYS="${DB_RETENTION_DAYS:-30}"
MEDIA_RETENTION_DAYS="${MEDIA_RETENTION_DAYS:-30}"
ALPINE_IMAGE="${ALPINE_IMAGE:-alpine:3.20}"
RCLONE_IMAGE="${RCLONE_IMAGE:-rclone/rclone:1.68.1}"
RCLONE_CONFIG="${RCLONE_CONFIG:-$HOME/.config/rclone/rclone.conf}"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"
RCLONE_DEST="${RCLONE_DEST:-PixelStandBackup}"
RCLONE_REMOTE_PATH="${RCLONE_REMOTE_PATH:-${RCLONE_REMOTE}:${RCLONE_DEST}}"

TS=$(date +%Y%m%d-%H%M%S)
mkdir -p "$DB_DIR" "$MEDIA_DIR"

# กัน cron ซ้อนกัน
LOCK_FILE="$BACKUP_ROOT/.backup.lock"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then log "⚠️ backup รอบก่อนยังไม่จบ — ข้าม"; exit 0; fi

TMP_DUMP="$DB_DIR/.db-${TS}.dump.part"
TMP_MEDIA="$MEDIA_DIR/.media-${TS}.tgz.part"
cleanup() { rm -f "$TMP_DUMP" "$TMP_MEDIA" 2>/dev/null || true; }
trap cleanup EXIT

log "🟢 เริ่ม backup pixelstand → $BACKUP_ROOT"

DB_CID=$(docker ps -q -f "name=^pixelstand_infra_db([.]|$)" | head -n1)
[ -n "$DB_CID" ] || die "ไม่พบ container pixelstand_infra_db ที่รันอยู่"

log "🐘 pg_dump ${POSTGRES_DB}…"
if ! docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$DB_CID" \
        pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$TMP_DUMP"; then
    die "pg_dump ล้มเหลว"
fi
[ -s "$TMP_DUMP" ] || die "pg_dump ได้ไฟล์ว่าง"
if ! docker exec -i "$DB_CID" pg_restore --list < "$TMP_DUMP" > /dev/null 2>&1; then
    die "ตรวจ dump ด้วย pg_restore --list ไม่ผ่าน"
fi
DB_FILE="$DB_DIR/db-${TS}.dump"
mv "$TMP_DUMP" "$DB_FILE"
log "✅ DB: $(basename "$DB_FILE") ($(du -h "$DB_FILE" | cut -f1))"

MEDIA_VOL="pixelstand_media_data"
if docker volume inspect "$MEDIA_VOL" > /dev/null 2>&1; then
    log "🖼️ tar volume $MEDIA_VOL…"
    if ! docker run --rm -v "$MEDIA_VOL":/media:ro "$ALPINE_IMAGE" \
            tar -C /media -czf - . > "$TMP_MEDIA"; then
        die "tar media volume ล้มเหลว"
    fi
    MEDIA_FILE="$MEDIA_DIR/media-${TS}.tgz"
    mv "$TMP_MEDIA" "$MEDIA_FILE"
    if ! tar -tzf "$MEDIA_FILE" > /dev/null 2>&1; then die "tar media อ่านกลับไม่ได้"; fi
    log "✅ Media: $(basename "$MEDIA_FILE") ($(du -h "$MEDIA_FILE" | cut -f1))"
else
    log "⚠️ ไม่พบ volume $MEDIA_VOL — ข้าม media"
fi

# retention
DEL_DB=$(find "$DB_DIR" -maxdepth 1 -type f -name '*.dump' -mtime +"$DB_RETENTION_DAYS" -print -delete | wc -l)
DEL_MEDIA=$(find "$MEDIA_DIR" -maxdepth 1 -type f -name '*.tgz' -mtime +"$MEDIA_RETENTION_DAYS" -print -delete | wc -l)
log "🧹 retention: ลบ dump $DEL_DB · media $DEL_MEDIA"

# offsite (ไม่บังคับ)
if [ ! -f "$RCLONE_CONFIG" ]; then
    log "⚠️ WARN offsite skipped — ไม่พบ $RCLONE_CONFIG (local สำเร็จแล้ว)"
    log "🟢 backup เสร็จสมบูรณ์ (local only)"; exit 0
fi

log "☁️ อัปโหลด offsite → $RCLONE_REMOTE_PATH"
RCLONE_DIR=$(dirname "$RCLONE_CONFIG")
RCLONE_RUN=(docker run --rm --user "$(id -u):$(id -g)" -v "$RCLONE_DIR":/config/rclone \
    -v "$BACKUP_ROOT":/backups:ro -e RCLONE_CONFIG=/config/rclone/rclone.conf -e HOME=/tmp "$RCLONE_IMAGE")

OFFSITE_OK=1
"${RCLONE_RUN[@]}" copy /backups/db "$RCLONE_REMOTE_PATH/db" --stats-one-line --stats 0 || OFFSITE_OK=0
if [ -d "$MEDIA_DIR" ]; then
    "${RCLONE_RUN[@]}" copy /backups/media "$RCLONE_REMOTE_PATH/media" --stats-one-line --stats 0 || OFFSITE_OK=0
fi
if [ "$OFFSITE_OK" -ne 1 ]; then
    log "❌ offsite upload ล้ม (local ยังครบ) — ตรวจ rclone config/เน็ต/quota"; exit 3
fi
log "🟢 backup เสร็จสมบูรณ์ (local + offsite)"
