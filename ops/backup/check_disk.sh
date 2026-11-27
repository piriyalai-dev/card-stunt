#!/usr/bin/env bash
# =============================================================================
# check_disk.sh — เฝ้าดิสก์และสุขภาพ backup (cron รายชั่วโมง) — single env pixelstand
#   CHECK_PATHS="/" · DISK_WARN_PCT=80 · DISK_CRIT_PCT=90 · BACKUP_MAX_AGE_HOURS=30
# exit: 0 = ปกติ/เตือน · 1 = วิกฤต
# =============================================================================
set -euo pipefail

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

CHECK_PATHS="${CHECK_PATHS:-/}"
DISK_WARN_PCT="${DISK_WARN_PCT:-80}"
DISK_CRIT_PCT="${DISK_CRIT_PCT:-90}"
BACKUP_ROOT="${BACKUP_ROOT:-$HOME/backups/pixelstand}"
BACKUP_MAX_AGE_HOURS="${BACKUP_MAX_AGE_HOURS:-30}"
RCLONE_CONFIG="${RCLONE_CONFIG:-$HOME/.config/rclone/rclone.conf}"
RCLONE_IMAGE="${RCLONE_IMAGE:-rclone/rclone:1.68.1}"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"

ALERTS=0
CRITICAL=0

for path in $CHECK_PATHS; do
    [ -d "$path" ] || { log "ALERT path '$path' ไม่มีอยู่"; ALERTS=$((ALERTS+1)); continue; }
    read -r used_pct avail < <(df -P "$path" | awk 'NR==2 {gsub("%","",$5); print $5, $4}')
    line="💽 $path ใช้ ${used_pct}% (เหลือ $((avail/1024/1024)) GB)"
    if [ "$used_pct" -ge "$DISK_CRIT_PCT" ]; then
        log "ALERT CRITICAL $line (≥${DISK_CRIT_PCT}%)"; CRITICAL=$((CRITICAL+1))
    elif [ "$used_pct" -ge "$DISK_WARN_PCT" ]; then
        log "ALERT WARN $line (≥${DISK_WARN_PCT}%)"; ALERTS=$((ALERTS+1))
    else
        log "OK $line"
    fi
done

# อายุ backup ล่าสุด
if [ -d "$BACKUP_ROOT/db" ]; then
    LATEST=$(find "$BACKUP_ROOT/db" -maxdepth 1 -type f -name '*.dump' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1)
    if [ -n "$LATEST" ]; then
        AGE_H=$(( ( $(date +%s) - $(echo "$LATEST" | cut -d' ' -f1 | cut -d. -f1) ) / 3600 ))
        if [ "$AGE_H" -gt "$BACKUP_MAX_AGE_HOURS" ]; then
            log "ALERT CRITICAL dump ล่าสุดอายุ ${AGE_H} ชม. (>${BACKUP_MAX_AGE_HOURS})"; CRITICAL=$((CRITICAL+1))
        else
            log "OK backup อายุ ${AGE_H} ชม."
        fi
    else
        log "ALERT ไม่พบ dump ใน $BACKUP_ROOT/db"; ALERTS=$((ALERTS+1))
    fi
else
    log "ℹ️ ยังไม่มี backup ที่ $BACKUP_ROOT"
fi

# docker df
log "$(docker system df 2>/dev/null | head -4 | tr '\n' ' ')"

# rclone quota (ถ้ามี config)
if [ -f "$RCLONE_CONFIG" ]; then
    RCLONE_DIR=$(dirname "$RCLONE_CONFIG")
    log "☁️ rclone quota:"
    docker run --rm --user "$(id -u):$(id -g)" -v "$RCLONE_DIR":/config/rclone \
        -e RCLONE_CONFIG=/config/rclone/rclone.conf -e HOME=/tmp "$RCLONE_IMAGE" \
        about "$RCLONE_REMOTE:" 2>/dev/null || log "  (อ่าน quota ไม่ได้)"
fi

log "ALERTS=$ALERTS CRITICAL=$CRITICAL"
[ "$CRITICAL" -eq 0 ] || exit 1
