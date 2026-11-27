# ops/backup — สำรองข้อมูลและซ้อมกู้คืน (Pixel Stand)

ชุดสคริปต์อยู่ **ใน repo** (ลอกแบบ pirivoice) · single env ไม่มี ENV_NAME · ไม่ต้อง sudo

| ไฟล์ | ใช้ทำอะไร | รันเมื่อไหร่ |
|---|---|---|
| `backup.sh` | pg_dump → media tar → retention → offsite (rclone) | cron วันละครั้ง |
| `check_disk.sh` | ดิสก์ 80/90% · อายุ backup · docker df · rclone quota | cron ทุกชั่วโมง |
| `restore.sh --dump …` | ซ้อมกู้บน scratch DB + scratch media | ก่อนขึ้น production / เดือนละครั้ง |
| `purge_media.sh [--apply]` | ลบ reference/thumbnail ที่ soft-delete เกิน 30 วัน + orphan | cron วันละครั้ง |
| `../../backend/scripts/verify_media.py` | เทียบ path ใน DB กับไฟล์จริง | เรียกผ่าน restore.sh |

## ติดตั้ง cron (ไม่ต้อง sudo)

```cron
# Pixel Stand — backup (02:30) + check_disk (:15) + purge (05:00)
30 2 * * * /home/singto1597/program_projects/card-stunt/ops/backup/backup.sh >> /home/singto1597/backups/pixelstand/backup.log 2>&1
15 * * * * /home/singto1597/program_projects/card-stunt/ops/backup/check_disk.sh >> /home/singto1597/backups/pixelstand/disk.log 2>&1
0 5 * * *  /home/singto1597/program_projects/card-stunt/ops/backup/purge_media.sh --apply >> /home/singto1597/backups/pixelstand/purge.log 2>&1
```

> ⚠️ cron มี PATH แคบ — สคริปต์เรียก `docker`, `find`, `tar`, `flock` จาก `/usr/bin` ทั้งหมด

## Offsite Google Drive (rclone — owner ทำครั้งเดียว)

เหมือน pirivoice `ops/backup/README.md` เปลี่ยนแค่ `RCLONE_DEST=PixelStandBackup`:

```bash
rclone config            # remote name: gdrive → scope 1 → browser auth
docker run --rm --user "$(id -u):$(id -g)" \
  -v ~/.config/rclone:/config/rclone -e RCLONE_CONFIG=/config/rclone/rclone.conf -e HOME=/tmp \
  rclone/rclone:1.68.1 mkdir gdrive:PixelStandBackup
```

## ซ้อมกู้คืน

```bash
cd /home/singto1597/program_projects/card-stunt
./ops/backup/restore.sh \
  --dump  "$(ls -t ~/backups/pixelstand/db/*.dump | head -1)" \
  --media "$(ls -t ~/backups/pixelstand/media/*.tgz | head -1)"
```

## สิ่งที่ backup ไม่รวม

- `.env` (มีความลับ) · Docker images/build cache (สร้างใหม่จาก pull_all.sh) · ไฟล์ใน `media/tmp/`
