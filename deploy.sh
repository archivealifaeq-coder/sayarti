#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo '== 1/4 سحب التحديثات =='
git pull

echo '== 2/4 الترحيلات (إن وجدت) =='
source venv/bin/activate
python manage.py migrate --noinput

echo '== 3/4 إصلاح تسمية الوقود الهجين =='
python manage.py shell -c "
from cars.models import CarSpecification as C
n = C.objects.filter(fuel='بنزين+كهرباء').count()
if n:
    print('تم تحويل', C.objects.filter(fuel='بنزين+كهرباء').update(fuel='هايبرد'), 'سجل')
else:
    print('لا توجد بيانات \"بنزين+كهرباء\"')
"

echo '== 4/4 إعادة تشغيل الموقع =='
systemctl restart gunicorn
systemctl status gunicorn --no-pager | head -n 4

echo
echo '=== نتيجة فحص كورولا (يجب أن تظهر بطاقات مثل بنزين خليجي / هايبرد صيني) ==='
python manage.py shell -c "
from django.db.models import Count
from cars.models import CarSpecification as C
qs = (C.objects.filter(model_ar__icontains='كورولا')
      .values('model_ar', 'fuel', 'spec_region').annotate(n=Count('id')).order_by('model_ar', 'fuel'))
if not qs:
    print('لا توجد بيانات كورولا على الخادم!')
for r in qs:
    print(r['model_ar'], '|', r['fuel'], '|', r['spec_region'], '|', r['n'])
"