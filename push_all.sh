#!/usr/bin/env bash
# ปล่อยโค้ดขึ้น Git remote (เหมือน pirivoice)
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "ใช้: ./push_all.sh \"ข้อความ commit\""; exit 1
fi

git add -A
git commit -m "$1"
git push origin "$(git branch --show-current)"

echo "✅ Push เรียบร้อย!"
