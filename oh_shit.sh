#!/usr/bin/env bash
# ⚠️ Rollback ฉุกเฉิน — ห่อ rollback.sh (สลับ image ไม่แตะ git)
#
# จงใจ **ไม่** ทำ `git reset --hard HEAD~1` แบบ pirivoice ตัวเก่า — การเขียนประวัติ
# checkout ทิ้งเป็นอันตราย (rollback.sh สลับ image เดิมที่ build ไว้แล้วแทน)
set -euo pipefail

cd "$(dirname "$0")"

echo "🚨 เริ่มกระบวนการกู้ภัยฉุกเฉิน (Rollback)!"

if [ $# -eq 0 ]; then
    echo "   ไม่ระบุ tag — แสดงรายการ image ที่มี:"
    ./rollback.sh --list
    echo
    echo "   ใช้: ./oh_shit.sh <image-tag>   (เช่น ./oh_shit.sh 9fbe3ad)"
    exit 1
fi

./rollback.sh "$1" --yes
echo "✅ กู้ภัยสำเร็จ! ระบบกลับไปใช้ image $1 แล้ว (checkout git ยังอยู่ที่เดิม)"
