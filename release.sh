#!/usr/bin/env bash
#
# release.sh — ตัด release ใหม่ (CHANGELOG → version files → manifest → commit → tag → push → GitHub Release)
# (ลอกแบบ pirivoice — เหมือนเดิมทุกขั้น เปลี่ยนแค่ REPO_SLUG/version files)
#
#   ./release.sh 0.2.0                  # release จริง
#   ./release.sh 0.2.0 --dry-run        # ตรวจทุกด่าน ไม่เขียน/ไม่ commit/ไม่ tag
#   ./release.sh 0.2.0-rc.1             # preview (ไม่แตะ CHANGELOG/VERSION)
set -euo pipefail

cd "$(dirname "$0")"

VERSION=""
REFS="main"
REFS_GIVEN=0
DRY_RUN=0
REPO_SLUG="piriyalai-dev/card-stunt"
DATE="$(TZ=Asia/Bangkok date +%Y-%m-%d)"

die() { echo "❌ $*" >&2; exit 1; }
ok()  { echo "✅ $*"; }
step() { echo; echo "▶ $*"; }

usage() { awk 'NR >= 2 && /^#/ { sub(/^# ?/, ""); print; next } NR >= 2 { exit }' "$0"; exit 0; }

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        --refs)    [ $# -ge 2 ] || die "--refs ต้องมีค่า"; REFS="$2"; REFS_GIVEN=1; shift 2 ;;
        -h|--help) usage ;;
        -*)        die "ไม่รู้จักตัวเลือก: $1" ;;
        *)         [ -z "$VERSION" ] || die "ระบุเวอร์ชันได้ครั้งเดียว"; VERSION="$1"; shift ;;
    esac
done

[ -n "$VERSION" ] || die "ใช้: ./release.sh <X.Y.Z> [--dry-run]"
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$ ]]; then
    die "เลขเวอร์ชันไม่ถูกรูปแบบ SemVer: $VERSION"
fi
IS_RC=0; [[ "$VERSION" == *-* ]] && IS_RC=1

step "ตรวจสภาพ repo"
if [ "$DRY_RUN" = "0" ]; then command -v gh >/dev/null 2>&1 || die "ไม่พบ gh (GitHub CLI)"; fi
command -v node >/dev/null 2>&1 || die "ไม่พบ node"
command -v npm >/dev/null 2>&1 || die "ไม่พบ npm"
[ "$(git branch --show-current)" = "main" ] || die "ต้องอยู่บน branch main"
[ -z "$(git status --porcelain)" ] || die "working tree ไม่สะอาด"
git fetch origin main --quiet
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || die "main ไม่ตรงกับ origin/main"
git rev-parse -q --verify "refs/tags/v$VERSION" >/dev/null && die "tag v$VERSION มีอยู่แล้ว"

PREV="$(git tag --list 'v*' --sort=-v:refname | head -1)"
[ -n "$PREV" ] || die "ไม่พบ tag ก่อนหน้า — สร้าง v0.1.0 ย้อนหลังก่อน (ดู docs/4-developer-playbook/versioning-and-releases.md)"
ok "tag ก่อนหน้า: $PREV"

# ตรวจว่าเลขเดินหน้าถูกขั้น (major/minor/patch) — เหมือน pirivoice
CURRENT="$(tr -d '[:space:]' < VERSION)"
[ "$CURRENT" = "${PREV#v}" ] || die "VERSION ($CURRENT) ไม่ตรงกับ tag ล่าสุด ($PREV)"
BUMP=""
if [ "$IS_RC" = "0" ]; then
    IFS=. read -r MA MI PA <<< "$VERSION"
    IFS=. read -r PMA PMI PPA <<< "${PREV#v}"
    if [ "$MA" -eq $((PMA + 1)) ] && [ "$MI" -eq 0 ] && [ "$PA" -eq 0 ]; then
        BUMP=major
    elif [ "$MA" -eq "$PMA" ] && [ "$MI" -eq $((PMI + 1)) ] && [ "$PA" -eq 0 ]; then
        BUMP=minor
    elif [ "$MA" -eq "$PMA" ] && [ "$MI" -eq "$PMI" ] && [ "$PA" -eq $((PPA + 1)) ]; then
        BUMP=patch
    else
        die "เลขเวอร์ชันต้องเดินทีละขั้นจาก $PREV: minor=$PMA.$((PMI+1)).0, patch=$PMA.$PMI.$((PPA+1)), major=$((PMA+1)).0.0"
    fi
    ok "เวอร์ชัน $VERSION (bump=$BUMP)"
fi

if [ "$REFS_GIVEN" = "0" ]; then
    DETECTED="$(git log --format=%s "$PREV..HEAD" | grep -oE 'Merge pull request #[0-9]+|\(#[0-9]+\)$' | grep -oE '[0-9]+' | sort -n -u | awk 'function flush(){if(!s)return;if(o++)printf ",";printf "PR #%d",s;if(l>s)printf "-#%d",l;s=0}{if(!s){s=l=$1;next}if($1==l+1){l=$1;next}flush();s=l=$1}END{flush();print ""}' || true)"
    if [ -n "$DETECTED" ]; then REFS="$DETECTED"; ok "ตรวจพบ PR: $REFS"; fi
fi

step "ตรวจ version manifest"
node scripts/version-manifest.mjs

step "อ่านชื่อรุ่นจาก CHANGELOG + ตัด CHANGELOG"
NOTES="$(mktemp)"
BACKUP_DIR=""; COMMITTED=0
VERSION_FILES="CHANGELOG.md VERSION backend/core/config.py frontend/package.json frontend/package-lock.json scripts/version-manifest.tsv"
if [ "$IS_RC" = "0" ]; then
    BACKUP_DIR="$(mktemp -d)"
    for f in $VERSION_FILES; do mkdir -p "$BACKUP_DIR/$(dirname "$f")"; cp "$f" "$BACKUP_DIR/$f"; done
fi
cleanup() {
    rm -f "$NOTES"
    if [ -n "$BACKUP_DIR" ]; then
        if [ "$COMMITTED" = "0" ]; then for f in $VERSION_FILES; do cp "$BACKUP_DIR/$f" "$f" 2>/dev/null || true; done; echo "↩ คืนไฟล์แล้ว"; fi
        rm -rf "$BACKUP_DIR"
    fi
}
trap cleanup EXIT

TITLE="$(python3 - "$VERSION" "$DATE" "$PREV" "$REPO_SLUG" "$NOTES" "$IS_RC" <<'PY'
import re, sys
version, date, prev, slug, notes_path, is_rc = sys.argv[1:7]
is_rc = is_rc == "1"
text = open("CHANGELOG.md", encoding="utf-8").read()
m = re.search(r"^## \[Unreleased\](?:[ \t]*—[ \t]*([^\n]*))?[ \t]*\n(.*?)(?=^## \[)", text, re.M | re.S)
if not m: sys.exit("ไม่พบ '## [Unreleased] — <ชื่อรุ่น>' ใน CHANGELOG.md")
title = (m.group(1) or "").strip(); body = m.group(2).strip()
if not title or title == "ยังไม่ตัดเวอร์ชัน": sys.exit("หัวข้อ [Unreleased] ยังไม่มีชื่อรุ่น")
if not body: sys.exit("section [Unreleased] ว่าง")
if "**Migration:**" not in body: sys.exit("ไม่มีบรรทัด **Migration:**")
notes = f"## v{version} — {date} — {title}\n\n{body}\n"
open(notes_path, "w", encoding="utf-8").write(notes)
if is_rc:
    print(title); sys.exit(0)
new_section = ("## [Unreleased] — ยังไม่ตัดเวอร์ชัน\n\n"
    f"## [{version}] — {date} — {title}\n\n" + body + "\n\n")
new = text[:m.start()] + new_section + text[m.end():]
old_link = f"[Unreleased]: https://github.com/{slug}/compare/{prev}...HEAD"
new_link = (f"[Unreleased]: https://github.com/{slug}/compare/v{version}...HEAD\n"
            f"[{version}]: https://github.com/{slug}/compare/{prev}...v{version}")
if old_link not in new: sys.exit("ไม่พบ compare link ของ [Unreleased]")
new = new.replace(old_link, new_link, 1)
open("CHANGELOG.md", "w", encoding="utf-8").write(new)
print(title)
PY
)"

[ -n "$TITLE" ] || die "อ่านชื่อรุ่นจาก CHANGELOG ไม่ได้"
[ -s "$NOTES" ] || die "notes ว่าง — ห้าม tag"
ok "ชื่อรุ่น: $TITLE"

if [ "$IS_RC" = "0" ]; then
    step "sync เลขเวอร์ชันเป็น $VERSION"
    echo "$VERSION" > VERSION
    python3 - "$VERSION" <<'PY'
import re, sys
v = sys.argv[1]
p = "backend/core/config.py"
s = open(p, encoding="utf-8").read()
new, n = re.subn(r'PROJECT_VERSION: str = "[^"]*"', f'PROJECT_VERSION: str = "{v}"', s, count=1)
if n != 1: sys.exit("ไม่พบ PROJECT_VERSION ใน backend/core/config.py")
open(p, "w", encoding="utf-8").write(new)
PY
    ( cd frontend && npm version "$VERSION" --no-git-tag-version --allow-same-version >/dev/null )
    ok "VERSION · config.py · package.json · package-lock.json = $VERSION"
    printf '%s\t%s\tRELEASE\t%s\t%s\t%s\n' "$VERSION" "$DATE" "$BUMP" "$TITLE" "$REFS" >> scripts/version-manifest.tsv
    step "preflight manifest"
    node scripts/version-manifest.mjs --preflight
fi

if [ "$DRY_RUN" = "1" ]; then
    step "dry-run — diff ที่จะ commit"
    git --no-pager diff --stat
    echo; echo "notes:"; sed 's/^/  /' "$NOTES" | head -20
    if [ -n "$BACKUP_DIR" ]; then for f in $VERSION_FILES; do cp "$BACKUP_DIR/$f" "$f"; done; rm -rf "$BACKUP_DIR"; BACKUP_DIR=""; fi
    [ -z "$(git status --porcelain)" ] || die "dry-run คืนไฟล์ไม่ครบ"
    ok "dry-run ผ่าน"; exit 0
fi

step "commit + tag"
if [ -n "$(git status --porcelain)" ]; then
    git add CHANGELOG.md VERSION backend/core/config.py frontend/package.json frontend/package-lock.json
    [ "$IS_RC" = "0" ] && git add scripts/version-manifest.tsv
    git commit -m "chore(release): v$VERSION"; ok "commit chore(release): v$VERSION"
else
    ok "ไฟล์เวอร์ชันตรงอยู่แล้ว"
fi
COMMITTED=1
git tag -a "v$VERSION" -m "v$VERSION — $DATE — $TITLE"
ok "annotated tag v$VERSION"
[ "$IS_RC" = "0" ] && node scripts/version-manifest.mjs

step "push main + tag"
git push origin main "v$VERSION"; ok "push แล้ว"

step "สร้าง GitHub Release"
if [ "$IS_RC" = "1" ]; then
    gh release create "v$VERSION" --verify-tag --prerelease --title "v$VERSION" --notes-file "$NOTES"
else
    gh release create "v$VERSION" --verify-tag --latest --title "v$VERSION" --notes-file "$NOTES"
fi
ok "ปล่อย v$VERSION เสร็จ — ต่อไป deploy ตามปกติ (pull_all.sh)"
