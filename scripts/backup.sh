#!/usr/bin/env bash
# ============================================================================
#  النسخ الاحتياطي الكامل اليومي — سيارتي (Sayarti)
#  يجهّز نسخة كاملة (شفرة + إعدادات + PostgreSQL + media) ويرفعها لمستودع
#  GitHub خاص (sayarti-full-backup) حتى لا يضيع الموقع أبداً حتى لو تلف الخادم.
#  يُشغَّل تلقائياً عبر cron كل ليلة، ويمكن تشغيله يدوياً:  bash backup.sh
# ============================================================================
set -euo pipefail

# ---- 0) إعدادات (عدّل إن لزم) ----------------------------------------------
APP_DIR="/var/www/sayarti"
BACKUP_NAME="sayarti-full-backup"
WORK_DIR="/tmp/sayarti_backup_$$"
BACKUP_DIR="${WORK_DIR}/artifact"
DATE_STAMP="$(date +%Y-%m-%d_%H%M%S)"

export PYTHONUTF8=1
cd "$APP_DIR"

# ---- 0.5) إعدادات GitHub (من .env) ------------------------------------------
GH_REPO="$(grep -E '^BACKUP_GITHUB_REPO=' .env | head -n1 | cut -d= -f2- | tr -d '"' || true)"
GH_TOKEN="$(grep -E '^GITHUB_BACKUP_TOKEN=' .env | head -n1 | cut -d= -f2- | tr -d '"' || true)"
ENC_PASS="$(grep -E '^BACKUP_ENCRYPTION_PASSPHRASE=' .env | head -n1 | cut -d= -f2- | tr -d '"' || true)"
ALLOW_LOCAL_ONLY="$(grep -E '^BACKUP_ALLOW_LOCAL_ONLY=' .env | head -n1 | cut -d= -f2- | tr -d '"' || true)"
ALLOW_UNENCRYPTED="$(grep -E '^BACKUP_ALLOW_UNENCRYPTED=' .env | head -n1 | cut -d= -f2- | tr -d '"' || true)"
KEEP_LAST="${BACKUP_KEEP_LAST:-7}"   # كم عدد النسخ المحفوظة في git (افتراضي 7)

# ---- 1) تجهيز -----------------------------------------------------------------
echo "== 1/7 تجهيز بنية النسخة =="
rm -rf "$WORK_DIR"
mkdir -p "$BACKUP_DIR/source"
mkdir -p "$BACKUP_DIR/media"
mkdir -p "$BACKUP_DIR/pg_dump"

# ---- 2) نسخ شفرة المصدر --------------------------------------------------------
echo "== 2/7 نسخ شفرة المصدر =="
cp -r cars config manage.py requirements.txt deploy.sh gunicorn.conf.py "$BACKUP_DIR/source/" 2>/dev/null || true
cp -r scripts "$BACKUP_DIR/source/" 2>/dev/null || true
cp -r staticfiles "$BACKUP_DIR/source/staticfiles" 2>/dev/null || true

# ---- 3) نسخ الإعدادات الحساسة (.env) ------------------------------------------
echo "== 3/7 نسخ ملفات الإعداد (.env) =="
cp .env "$BACKUP_DIR/source/.env" 2>/dev/null || echo "  (لا يوجد .env — يُضاف يدوياً عند الاسترجاع)"

# ---- 4) تفريغ قاعدة بيانات PostgreSQL -----------------------------------------
echo "== 4/7 تفريغ قاعدة بيانات PostgreSQL =="
DB_URL="$(grep -E '^DATABASE_URL=' .env | head -n1 | cut -d= -f2- | tr -d '"' || true)"
if [ -n "$DB_URL" ]; then
  DB_REST="${DB_URL#*://}"
  DB_PASS="${DB_REST%%@*}"; DB_PASS="${DB_PASS#*:}"
  DB_USER="${DB_REST%%@*}"; DB_USER="${DB_USER%%:*}"
  DB_HOSTPORT="${DB_REST##*@}"
  DB_HOST="$(echo "$DB_HOSTPORT" | cut -d/ -f1 | cut -d: -f1)"
  DB_NAME="$(echo "$DB_HOSTPORT" | cut -d/ -f2 | cut -d? -f1)"
  # ملاحظة: لا نقتبس BASE_URL داخل النص المسرّب في OS يجب أن ننتبه للكلمة.
  # نقوم بالتفريغ باستخدام pg_dump مع كلمة المرور عبر المتغير PGPASSWORD.
  PGPASSWORD="$DB_PASS" pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" \
      --no-owner --no-privileges -Fc -f "$BACKUP_DIR/pg_dump/sayarti_pg_${DATE_STAMP}.dump" \
      && echo "  تم تفريغ PostgreSQL"
else
  echo "  لا توجد DATABASE_URL — أُجرّب SQLite"
  cp db.sqlite3 "$BACKUP_DIR/pg_dump/db.sqlite3.backup" 2>/dev/null || true
fi

# ---- 5) نسخ media -------------------------------------------------------------
echo "== 5/7 نسخ media =="
cp -r media/* "$BACKUP_DIR/media/" 2>/dev/null || echo "  (فارغ)"

# ---- 6) الضغط ------------------------------------------------------------------
echo "== 6/7 ضغط النسخة =="
cd "$WORK_DIR"
tar -czf "${BACKUP_NAME}_${DATE_STAMP}.tar.gz" artifact
BACKUP_FILE="${BACKUP_NAME}_${DATE_STAMP}.tar.gz"
if [ -n "$ENC_PASS" ]; then
  echo "  تشفير النسخة قبل الرفع"
  openssl enc -aes-256-cbc -salt -pbkdf2 -in "$BACKUP_FILE" -out "${BACKUP_FILE}.enc" -pass pass:"$ENC_PASS"
  rm -f "$BACKUP_FILE"
  BACKUP_FILE="${BACKUP_FILE}.enc"
elif [ "${ALLOW_UNENCRYPTED,,}" != "true" ]; then
  echo "❌ BACKUP_ENCRYPTION_PASSPHRASE غير مضبوط. لن أرفع نسخة غير مشفرة تحتوي .env."
  echo "   اضبط BACKUP_ENCRYPTION_PASSPHRASE أو BACKUP_ALLOW_UNENCRYPTED=true عن قصد."
  exit 2
fi
ls -lh "$BACKUP_FILE"

# ---- 7) الرفع إلى مستودع GitHub الخاص ------------------------------------------
echo "== 7/7 الرفع إلى GitHub =="
if [ -z "$GH_TOKEN" ] || [ -z "$GH_REPO" ]; then
  echo "❌ توكن/مستودع النسخ غير مضبوط — لم تُرفع النسخة."
  echo "   أضف في .env: BACKUP_GITHUB_REPO و GITHUB_BACKUP_TOKEN."
  echo "   النسخة المحلية المؤقتة: ${WORK_DIR}/${BACKUP_FILE}"
  if [ "${ALLOW_LOCAL_ONLY,,}" = "true" ]; then
    echo "   BACKUP_ALLOW_LOCAL_ONLY=true لذلك لن أعتبرها فشلاً."
    exit 0
  fi
  exit 3
fi

# مستودع git مؤقت (خاص) للنسخ: نسحب الموجود أولاً حتى لا يرفض GitHub الدفع برسالة fetch first.
GIT_DIR="${WORK_DIR}/gitrepo"
REMOTE_URL="https://x-access-token:${GH_TOKEN}@github.com/${GH_REPO}.git"
if ! git clone -q "$REMOTE_URL" "$GIT_DIR" 2>/dev/null; then
  mkdir -p "$GIT_DIR"
  git -C "$GIT_DIR" init -q 2>/dev/null || true
  git -C "$GIT_DIR" remote remove origin 2>/dev/null || true
  git -C "$GIT_DIR" remote add origin "$REMOTE_URL"
fi

# نسخ ملف النسخة الجديد إلى مستودع النسخ مع تسمية موحدة (نبقّي التاريخ في اسم)
git -C "$GIT_DIR" config user.email "backup@srv.local"
git -C "$GIT_DIR" config user.name "Sayarti Backup"
mkdir -p "$GIT_DIR/backups"
cp "$BACKUP_FILE" "$GIT_DIR/backups/"

# الحفاظ على آخر KEEP_LAST نسخ فقط (حذف الأقدم في git)
(cd "$GIT_DIR/backups" && ls -1t *.tar.gz *.tar.gz.enc 2>/dev/null | tail -n +$((KEEP_LAST+1)) | while read -r old; do rm -f "$old"; done)

git -C "$GIT_DIR" add -A
if git -C "$GIT_DIR" diff --cached --quiet; then
  echo "  لا توجد تغييرات جديدة للرفع."
else
  git -C "$GIT_DIR" commit -q -m "backup $DATE_STAMP"
fi

BRANCH="$(git -C "$GIT_DIR" branch --show-current 2>/dev/null || true)"
if [ -z "$BRANCH" ]; then
  BRANCH="master"
fi
git -C "$GIT_DIR" push -q origin "HEAD:${BRANCH}"

echo "✅ اكتمل: ${BACKUP_FILE} رُفع إلى github.com/${GH_REPO}"

# ---- تنظيف ----------------------------------------------------------------------
rm -rf "$WORK_DIR"
find /tmp -maxdepth 1 \( -name "${BACKUP_NAME}_*.tar.gz" -o -name "${BACKUP_NAME}_*.tar.gz.enc" \) -mtime +$KEEP_LAST -delete 2>/dev/null || true
echo "انتهى."
