#!/usr/bin/env bash
# الانتقال من SQLite إلى PostgreSQL — يُنفَّذ على الخادم مرة واحدة فقط.
#
# المتطلبات قبل تشغيله (يدوياً مرة واحدة):
#   sudo apt install postgresql
#   sudo -u postgres psql -c "CREATE USER sayarti WITH PASSWORD 'ضع_كلمة_مرور_قوية';"
#   sudo -u postgres psql -c "CREATE DATABASE sayarti OWNER sayarti;"
# ثم أضف في /var/www/sayarti/.env:
#   DATABASE_URL=postgres://sayarti:كلمة_المرور@127.0.0.1:5432/sayarti
#
# ملاحظة: السكربت يُصدّر من SQLite أولاً (قبل تفعيل المتغير) ثم يستورد إلى
# PostgreSQL، أي أن البيانات القديمة لا تُفقد ولا تُكرَّر.
set -euo pipefail
cd "$(dirname "$0")/.."

# ضمان UTF-8 حتى على الخوادم التي `LC_ALL=C` (وإلا يفشل التصدير على الحروف العربية)
export PYTHONUTF8=1

source venv/bin/activate

PG_URL="$(grep -E '^DATABASE_URL=' .env 2>/dev/null | head -n1 | cut -d= -f2- | tr -d '"' || true)"
if [ -z "${PG_URL:-}" ]; then
  echo "خطأ: DATABASE_URL غير موجودة في .env — أضفها أولاً (انظر مقدمة السكربت)."
  exit 1
fi

echo '== 1/6 تصدير بيانات SQLite الحالية =='
unset DATABASE_URL
# نستثني: سجل إدارة + جلسات (مؤقتة)، والـ contenttypes/perms تُنشأ تلقائياً بـ migrate
# (إبقاء admin.logentry سيكسر الاستيراد: يشير إلى contenttypes المستبعدة)
python manage.py dumpdata \
  --exclude=contenttypes --exclude=auth.permission \
  --exclude=admin.logentry --exclude=sessions.session \
  -o /tmp/sayarti_dump.json
echo "تم التصدير: $(wc -c < /tmp/sayarti_dump.json) بايت"

echo '== 2/6 التبديل إلى PostgreSQL =='
export DATABASE_URL="$PG_URL"

echo '== 3/6 إنشاء الجداول =='
python manage.py migrate --noinput
python manage.py createcachetable django_cache_shared

echo '== 4/6 استيراد البيانات إلى PostgreSQL =='
python manage.py loaddata /tmp/sayarti_dump.json

echo '== 5/6 مزامنة المتسلسلات (حتى لا تصطدم الترقيمات القادمة) =='
python manage.py shell -c "
from django.db import connection
with connection.cursor() as c:
    c.execute(\"SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='S' AND n.nspname='public'\")
    seqs = [r[0] for r in c.fetchall()]
    for seq in seqs:
        table = seq[:-8] if seq.endswith('_id_seq') else seq
        c.execute('SELECT setval(%s, COALESCE((SELECT MAX(id) FROM \"' + table + '\"), 1))', [seq])
        print('مزامنة:', seq)
print('عدد المتسلسلات:', len(seqs))
"

echo '== 6/6 فحص سريع =='
python manage.py shell -c "
from cars.models import CarSpecification, Sponsor, PromoCode
print('cars:', CarSpecification.objects.count(), '| sponsors:', Sponsor.objects.count(), '| codes:', PromoCode.objects.count())
"

echo 'انتهى — الموقع يعمل الآن على PostgreSQL.'