import re
from pathlib import Path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q, Count, F
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.core.cache import cache, caches
from .models import (
    CarSpecification, AdBanner, SiteSettings, Sponsor, PromoCode, Dealer,
    AppInstallMetric, DealerClickMetric, CarSymptom, MaintenanceTask,
)
from .services.textnorm import fold_ar, fold_engine


SW_FILE = Path(__file__).resolve().parent / 'static' / 'shared' / 'sw.js'


def manifest_view(request):
    manifest = {
        "name": "\u0633\u064a\u0627\u0631\u062a\u064a - \u062f\u0644\u064a\u0644 \u0645\u0648\u0635\u0641\u0627\u062a \u0627\u0644\u0633\u064a\u0627\u0631\u0627\u062a \u0627\u0644\u0630\u0643\u064a",
        "short_name": "\u0633\u064a\u0627\u0631\u062a\u064a",
        "description": "\u062f\u0644\u064a\u0644 \u0645\u0648\u0635\u0641\u0627\u062a \u0627\u0644\u0633\u064a\u0627\u0631\u0627\u062a - \u0645\u0648\u0635\u0641\u0627\u062a\u060c \u0632\u064a\u0648\u062a\u060c \u0625\u0637\u0627\u0631\u0627\u062a\u060c \u0648\u062a\u0648\u0635\u064a\u0627\u062a \u0644\u0643\u0644 \u0633\u064a\u0627\u0631\u0629.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#0f172a",
        "dir": "rtl",
        "lang": "ar",
        "orientation": "portrait-primary",
        "categories": ["automotive", "utilities"],
        "icons": [
            {"src": "/static/shared/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/static/shared/icons/apple-touch-icon.png", "sizes": "180x180", "type": "image/png", "purpose": "any"},
            {"src": "/static/shared/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/static/shared/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        "prefer_related_applications": False,
    }
    return JsonResponse(manifest)


def sw_view(request):
    code = SW_FILE.read_text(encoding='utf-8') if SW_FILE.exists() else ''
    response = HttpResponse(code, content_type='application/javascript; charset=utf-8')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'public, max-age=0, must-revalidate'
    return response


def _safe_int(value, default=0):
    try:
        return max(0, int(str(value).replace(',', '').strip()))
    except (TypeError, ValueError):
        return default


def _maintenance_due_status(task, odometer):
    if odometer < task.start_km:
        km_to_stage = task.start_km - odometer
        if km_to_stage <= 3000:
            return 'soon', f'قريبة بعد حوالي {km_to_stage:,} كم'
        return 'later', f'تبدأ عادة قرب {task.start_km:,} كم'
    if (task.interval_km or 0) >= 999999 and (task.severe_interval_km or 0) >= 999999:
        km_after_stage = odometer - task.start_km
        if km_after_stage <= 3000:
            return 'due', 'مستحقة ضمن مرحلة الصيانة الحالية'
        return 'ok', 'مرحلة صيانة سابقة'
    interval = task.severe_interval_km or task.interval_km or 1
    distance_since_start = odometer - task.start_km
    remainder = distance_since_start % interval
    km_to_next = interval - remainder if remainder else 0
    if remainder == 0 or km_to_next <= 1000:
        return 'due', 'مستحقة الآن أو قريبة جداً'
    if km_to_next <= 3000:
        return 'soon', f'قريبة بعد حوالي {km_to_next:,} كم'
    return 'ok', f'المراجعة القادمة بعد حوالي {km_to_next:,} كم'


def _maintenance_display_level(task):
    text = f'{task.category} {task.name} {task.condition_type}'.lower()
    conditional_words = ('دبل', 'دفرنشل', 'كورنة', 'ترانسفير', 'درايم', 'كردان', 'هايبرد', 'تيربو', 'ديزل', 'cvt')
    check_due_words = ('قير', 'كير', 'ناقل', 'بواجي', 'كويل', 'قايش', 'سير', 'رولات', 'سائل')
    if task.condition_type in {'drivetrain', 'hybrid', 'turbo', 'diesel', 'cvt', 'engine', 'transmission'} or any(word in text for word in conditional_words):
        return 'conditional'
    if task.condition_type == 'manufacturer_schedule' or task.category in {'transmission', 'belts', 'ignition'} or any(word in text for word in check_due_words):
        return 'check_due'
    return task.display_level or 'essential'


def _unique_texts(values):
    seen = set()
    result = []
    for value in values:
        text = str(value).strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def _split_pipe_lines(value):
    if not value:
        return []
    parts = re.split(r'[|\r\n]+', str(value))
    return [part.strip(' \t-–—') for part in parts if part.strip(' \t-–—')]


def _build_maintenance_summary(odometer, nearest_km, engine_type, transmission, stage_tasks=None):
    if not odometer:
        return None
    stage_title = f'صيانة قريبة من {nearest_km:,} كم' if nearest_km else f'صيانة حسب ممشى {odometer:,} كم'
    delta = odometer - nearest_km if nearest_km else 0
    if nearest_km and delta == 0:
        stage_note = 'أنت على مرحلة الصيانة نفسها تقريباً.'
    elif nearest_km and delta > 0:
        stage_note = f'أقرب مرحلة صيانة أقل من ممشاك بفارق {delta:,} كم.'
    elif nearest_km:
        stage_note = f'أقرب مرحلة صيانة جاية بعد {abs(delta):,} كم.'
    else:
        stage_note = 'هذه توصيات عامة لأن بيانات المرحلة التفصيلية غير متوفرة.'

    essential = [
        'بدّل زيت المحرك وفلتر الزيت إذا وصل موعدهما، ولا تطوّل أكثر من 5,000 كم بالاستخدام الشاق داخل العراق إلا إذا توصية الشركة أقصر.',
        'افحص الفرامل والإطارات وضغط الهواء، ودوّر الإطارات تقريباً كل 10,000 كم إذا يسمح تصميم السيارة ونمط التآكل.',
        'افحص مستوى سائل التبريد والدبة والرديتر والخراطيم، ولا تفتح غطاء التبريد والمحرك حار.',
        'افحص البطارية ونظام الشحن خصوصاً قبل الصيف، لأن الحرارة تقصر عمر البطارية بشكل واضح.',
        'استبدل فلتر هواء المحرك وفلتر المكيف عند الاتساخ، التنظيف ما يعوض الفلتر إذا ضعفت كفاءة الفلترة.',
    ]

    stage_tasks = stage_tasks or []
    stage_check_due = _unique_texts(
        task.name for task in stage_tasks
        if _maintenance_display_level(task) == 'check_due' or str(task.action_type).strip() == 'فحص'
    )
    stage_conditional = _unique_texts(
        task.name for task in stage_tasks if _maintenance_display_level(task) == 'conditional'
    )

    if stage_check_due:
        check_due = [
            f'{name}: تحقق من جدول الشركة وحالة القطعة قبل التبديل.'
            for name in stage_check_due
        ]
    else:
        check_due = []

    conditional = [
        f'{name}: يظهر فقط إذا كانت هذه المنظومة موجودة بسيارتك أو تنطبق على نوع محركك/الكير.'
        for name in stage_conditional
    ]
    if engine_type == 'gasoline_turbo':
        conditional.append('إذا سيارتك تيربو، افحص صوندات التيربو والانتركولر وأي تهريب هواء أو زيت مع ضعف العزم.')
    if engine_type == 'hybrid':
        conditional.append('إذا سيارتك هايبرد، تابع فلتر/مجرى تبريد بطارية الهايبرد ونظافة فتحات التهوية.')
    if engine_type == 'diesel':
        conditional.append('إذا سيارتك ديزل، تابع فلتر الوقود/فاصل الماء وجودة الوقود لأن تأثيرها مباشر على البخاخات.')
    if transmission == 'cvt':
        conditional.append('إذا الكير CVT، لا تستخدم زيت عام، اتبع مواصفة الشركة حرفياً لأن حساسية هذا الكير عالية.')
    elif transmission in {'automatic', 'dct', 'ecvt', 'amt'}:
        conditional.append('إذا الكير أوتوماتيك أو DCT/e-CVT، فحص الزيت يكون حسب طريقة الشركة ودرجة الحرارة المحددة، مو بقياس عشوائي.')
    if not stage_conditional:
        conditional.append('إذا سيارتك دبل/دفرنس/ترانسفير، افحص التسريبات والأصوات واستحقاق الزيت حسب جدول الشركة.')

    fixed_notes = [
        'الزيت والفلاتر: بدّل زيت المحرك وفلتر الزيت كل 5,000 كم بالاستخدام الشاق في العراق أو حسب توصية الشركة إذا كانت أقصر، واستبدل فلاتر الهواء والمكيف عند الاتساخ بدل الاكتفاء بتنظيفها إذا ضعفت كفاءتها.',
        'الإطارات: افحص ضغط الإطارات وهي باردة، ودوّر أماكن الإطارات تقريباً كل 10,000 كم إذا يسمح تصميم السيارة ونمط التآكل. أي تآكل غير متساوٍ يحتاج فحص زوايا وتعليق.',
        'التبريد: تابع مستوى سائل التبريد في الدبة وافحص الرديتر والخراطيم والمراوح، ولا تفتح غطاء الرديتر والمحرك حار. استخدم سائل تبريد مطابق لمواصفة السيارة.',
        'البطارية والشحن: افحص البطارية والدينمو والتوصيلات خصوصاً قبل الصيف، حرارة العراق تقلل عمر البطارية وتزيد حساسية نقاط التأريض والشحن.',
        'هذه التوصيات عامة ومقصودها تساعدك ترتب الأولويات، دليل الشركة يبقى المرجع الأول للمواصفات والفترات الدقيقة.',
        'أجواء العراق تعتبر استخدام شاق: حرارة، غبار، ازدحام، وتشغيل مكيف طويل، لذلك الفحص المبكر أفضل من الانتظار لنهاية الفترة.',
        'إذا ظهرت لمبة زيت، حرارة عالية، دخان كثيف، رائحة وقود، أو فقدان قوي بالعزم، أوقف السيارة وراجع مختص فوراً.',
    ]

    return {
        'stage_title': stage_title,
        'stage_note': stage_note,
        'essential': essential,
        'check_due': check_due,
        'conditional': conditional,
        'fixed_notes': fixed_notes,
    }


def maintenance_view(request):
    symptom_slug = request.GET.get('symptom', '').strip()
    odometer = _safe_int(request.GET.get('odometer'))
    maintenance_brand = request.GET.get('maintenance_brand', '').strip()
    engine_type = request.GET.get('engine_type', 'all').strip() or 'all'
    transmission = request.GET.get('transmission', 'all').strip() or 'all'

    symptoms = CarSymptom.objects.filter(is_active=True).prefetch_related('causes')
    selected_symptom = None
    if symptom_slug:
        selected_symptom = symptoms.filter(slug=symptom_slug).first()

    maintenance_rows = []
    maintenance_summary = None
    brand_values = set()
    for item in MaintenanceTask.objects.filter(is_active=True).values('brand_ar', 'brand_en').distinct():
        brand = item.get('brand_ar') or item.get('brand_en')
        if brand and brand != 'عام':
            brand_values.add(brand)
    maintenance_brand_choices = sorted(brand_values)

    if odometer:
        tasks = MaintenanceTask.objects.filter(is_active=True)
        if maintenance_brand:
            tasks = tasks.filter(Q(brand_ar='') | Q(brand_en='') | Q(brand_ar=maintenance_brand) | Q(brand_en=maintenance_brand))
        else:
            tasks = tasks.filter(Q(brand_ar='', brand_en='') | Q(brand_ar='عام'))
        tasks = tasks.filter(
            Q(applies_to_engine_type='all') | Q(applies_to_engine_type=engine_type)
        ).filter(
            Q(applies_to_transmission='all') | Q(applies_to_transmission=transmission)
        )
        task_list = list(tasks)
        specific_keys = {
            (task.name.strip().lower(), task.category, task.applies_to_engine_type, task.applies_to_transmission)
            for task in task_list
            if maintenance_brand and (task.brand_ar or task.brand_en)
        }
        candidate_tasks = []
        for task in task_list:
            task_key = (task.name.strip().lower(), task.category, task.applies_to_engine_type, task.applies_to_transmission)
            if maintenance_brand and not (task.brand_ar or task.brand_en) and task_key in specific_keys:
                continue
            candidate_tasks.append(task)

        if candidate_tasks:
            stage_values = {task.start_km for task in candidate_tasks}
            nearest_km = min(stage_values, key=lambda km: (abs(km - odometer), 0 if km >= odometer else 1, km))
            distance = odometer - nearest_km
            if distance == 0:
                status = 'due'
                note = 'مرحلة الممشى الحالية'
            elif distance > 0:
                status = 'due'
                note = f'أقرب مرحلة للممشى بفارق {distance:,} كم'
            else:
                status = 'soon'
                note = f'أقرب مرحلة للممشى بفارق {abs(distance):,} كم'
            for task in candidate_tasks:
                if task.start_km == nearest_km:
                    maintenance_rows.append({'task': task, 'status': status, 'status_note': note})
            maintenance_rows.sort(key=lambda row: (row['task'].category, row['task'].name))
            maintenance_summary = _build_maintenance_summary(
                odometer,
                nearest_km,
                engine_type,
                transmission,
                [row['task'] for row in maintenance_rows],
            )
        else:
            maintenance_summary = _build_maintenance_summary(odometer, None, engine_type, transmission)

    maintenance_groups = []
    grouped = {}
    for row in maintenance_rows:
        task = row['task']
        title = task.stage_title or f'مرحلة {task.start_km:,} كم'
        key = (title, row['status'], row['status_note'])
        if key not in grouped:
            grouped[key] = {
                'title': title,
                'status': row['status'],
                'status_note': row['status_note'],
                'tasks': [],
                'essential_tasks': [],
                'check_due_tasks': [],
                'conditional_tasks': [],
            }
            maintenance_groups.append(grouped[key])
        grouped[key]['tasks'].append(task)
        display_level = _maintenance_display_level(task)
        if display_level == 'check_due':
            grouped[key]['check_due_tasks'].append(task)
        elif display_level == 'conditional':
            grouped[key]['conditional_tasks'].append(task)
        else:
            grouped[key]['essential_tasks'].append(task)

    return render(request, 'cars/maintenance.html', {
        'symptoms': symptoms,
        'selected_symptom': selected_symptom,
        'odometer': odometer or '',
        'maintenance_brand': maintenance_brand,
        'maintenance_brand_choices': maintenance_brand_choices,
        'engine_type': engine_type,
        'engine_type_choices': MaintenanceTask.APPLIES_CHOICES,
        'transmission': transmission,
        'transmission_choices': MaintenanceTask.TRANSMISSION_CHOICES,
        'maintenance_rows': maintenance_rows,
        'maintenance_groups': maintenance_groups,
        'maintenance_summary': maintenance_summary,
    })


def symptom_detail(request, slug):
    symptom = CarSymptom.objects.filter(slug=slug, is_active=True).prefetch_related('causes').first()
    if not symptom:
        return redirect('maintenance')
    active_causes = [cause for cause in symptom.causes.all() if cause.is_active]
    return render(request, 'cars/maintenance_symptom_detail.html', {
        'symptom': symptom,
        'active_causes': active_causes,
        'driver_questions': _split_pipe_lines(symptom.driver_questions),
        'self_check_steps': _split_pipe_lines(symptom.self_check_steps),
    })


RELAX_LABELS = {
    'spec_region': '\u0645\u0648\u0627\u0635\u0641\u0627\u062a \u0627\u0644\u0645\u0646\u0637\u0642\u0629',
    'engine_type': '\u0646\u0648\u0639 \u0627\u0644\u0645\u062d\u0631\u0643',
    'year': '\u0633\u0646\u0629 \u0627\u0644\u0635\u0646\u0639',
    'engine': '\u0633\u0639\u0629 \u0627\u0644\u0645\u062d\u0631\u0643',
    'fuel': '\u0646\u0648\u0639 \u0627\u0644\u0648\u0642\u0648\u062f',
    'trim': '\u0627\u0644\u0641\u0626\u0629',
}


def _exact_text_q(ar_field, en_field, value):
    normalized = fold_ar(value)
    return Q(**{ar_field: normalized}) | Q(**{f'{en_field}__iexact': value})


def _filters(request):
    brand = request.GET.get('brand', '').strip()
    model = request.GET.get('model', '').strip()
    year = request.GET.get('year', '').strip()
    engine = request.GET.get('engine', '').strip()
    engine_type = request.GET.get('engine_type', '').strip()
    spec_region = request.GET.get('spec_region', '').strip()
    fuel = request.GET.get('fuel', '').strip()
    vehicle_identity_complete = all((brand, model, year, spec_region))
    has_vehicle_query = any((brand, model, year, engine, engine_type, fuel))

    required = Q()
    if brand:
        b = fold_ar(brand)
        required &= Q(brand_norm__icontains=b) | Q(brand_en__icontains=brand)
    if model:
        m = fold_ar(model)
        required &= Q(model_norm__icontains=m) | Q(model_en__icontains=model)
    if year:
        try:
            required &= Q(year=int(year))
        except ValueError:
            required &= Q(pk__isnull=True)

    optional = []
    if engine_type:
        optional.append(('engine_type', Q(engine_type=engine_type)))
    if spec_region:
        optional.append(('spec_region', Q(spec_region=spec_region)))
    if fuel:
        f = fold_ar(fuel)
        optional.append(('fuel', Q(fuel__iexact=fuel) | Q(fuel=f)))
    if engine:
        if not vehicle_identity_complete:
            # لا يجوز فصل المحرك عن سنته وسوقه حتى عبر رابط GET يدوي.
            required &= Q(pk__isnull=True)
        else:
            # القائمة ترسل الاسم الكامل؛ المطابقة التقريبية تخلط أنظمة الدفع
            # التي تشترك في السعة وكود المحرك.
            optional.append(('engine', Q(engine__iexact=engine)))
    if has_vehicle_query and not spec_region:
        # المواصفة/السوق جزء إلزامي من هوية السيارة، وليست فلتر تحسين اختياري.
        required &= Q(pk__isnull=True)
    return required, optional


def _apply(qs, required, keep_keys):
    q = required
    for key, cond in keep_keys:
        q &= cond
    if q == Q():
        return qs.none()
    return qs.filter(q)


def _split_list_values(value):
    """حوّل ماركات الزيت إلى قائمة؛ كل قيمة داخل قوسين تعد ماركة مستقلة."""
    if not value:
        return []
    text = str(value)
    bracket_items = re.findall(r'\(([^()]+)\)', text)
    if bracket_items:
        raw_items = []
        for chunk in bracket_items:
            raw_items.extend(re.split(r'[\r\n,،;؛|]+', chunk))
    else:
        raw_items = re.split(r'[\r\n,،;؛|]+', text)

    items = []
    seen = set()
    for item in raw_items:
        item = item.strip(' \t-–—()')
        normalized = item.casefold()
        if item and normalized not in seen:
            seen.add(normalized)
            items.append(item)
    return items


def _group_search_results(cars, selected_engine='', selected_engine_type=''):
    """اجمع صفوف المحركات في بطاقة سيارة واحدة من دون تغيير جدول السيارات.

    البطاقة تمثل الماركة/الموديل/السنة/السوق، وداخلها تُجمع
    المحركات التي تحمل التوصية الفنية نفسها. لا تُستنتج أي معلومة جديدة؛
    كل قيمة معروضة مأخوذة من صف CarSpecification موجود فعلاً.
    """
    if cars is None:
        return None

    groups = {}
    for car in cars:
        group_key = (
            car.brand_ar, car.brand_en, car.model_ar, car.model_en,
            car.year, car.spec_region,
        )
        group = groups.setdefault(group_key, {
            'id': car.id,
            'car': car,
            'engines': [],
            'recommendations': [],
            '_engine_keys': set(),
            '_engine_map': {},
            '_recommendation_map': {},
        })

        # نص المحرك الكامل جزء من الهوية؛ engine_norm يزيل تفاصيل مثل FWD/AWD
        # ولذلك لا يصلح مفتاحاً لتجميع التوصيات.
        engine_key = (car.engine.casefold(), car.engine_code or '', car.engine_type)
        engine_data = {
            'id': car.id,
            'name': car.engine,
            'code': car.engine_code or '',
            'type': car.engine_type,
            'type_label': car.get_engine_type_display(),
            'recommendations': [],
            '_recommendation_keys': set(),
        }
        if engine_key not in group['_engine_keys']:
            group['_engine_keys'].add(engine_key)
            group['engines'].append(engine_data)
            group['_engine_map'][engine_key] = engine_data
        else:
            engine_data = group['_engine_map'][engine_key]

        recommendation_key = (
            engine_key,
            car.oil_visc, car.oil_capacity, car.fuel, car.octane,
            car.oil_visc_high_km or '', car.oil_brands or '',
            car.transmission_type or '', car.transmission_oil_spec or '',
            car.transmission_oil_brands or '', car.recommendations or '',
            car.tire_size or '', car.spark or '', car.battery or '', car.trim or '',
        )
        recommendation = group['_recommendation_map'].get(recommendation_key)
        if recommendation is None:
            recommendation = {
                'car': car,
                'oil_brand_items': _split_list_values(car.oil_brands),
                'transmission_oil_brand_items': _split_list_values(car.transmission_oil_brands),
                'engines': [],
                '_engine_keys': set(),
            }
            group['_recommendation_map'][recommendation_key] = recommendation
            group['recommendations'].append(recommendation)
        if engine_key not in recommendation['_engine_keys']:
            recommendation['_engine_keys'].add(engine_key)
            recommendation['engines'].append({
                'id': engine_data['id'],
                'name': engine_data['name'],
                'code': engine_data['code'],
                'type': engine_data['type'],
                'type_label': engine_data['type_label'],
            })
        if recommendation_key not in engine_data['_recommendation_keys']:
            engine_data['_recommendation_keys'].add(recommendation_key)
            engine_data['recommendations'].append(recommendation)

    result = []
    for group in groups.values():
        group.pop('_engine_keys', None)
        group.pop('_engine_map', None)
        group.pop('_recommendation_map', None)
        for recommendation in group['recommendations']:
            recommendation.pop('_engine_keys', None)
        for engine_data in group['engines']:
            engine_data.pop('_recommendation_keys', None)
        group['engine_count'] = len(group['engines'])
        group['selected_engine_id'] = None
        if group['engine_count'] == 1:
            group['selected_engine_id'] = group['engines'][0]['id']
        elif selected_engine:
            for engine_data in group['engines']:
                name_matches = engine_data['name'].casefold() == selected_engine.casefold()
                type_matches = not selected_engine_type or engine_data['type'] == selected_engine_type
                if name_matches and type_matches:
                    group['selected_engine_id'] = engine_data['id']
                    break
        result.append(group)
    return result


def _cached_lookup_data():
    """بيانات القوائم الثابتة (البراندات/الفئات/...)— محسوبة مرة وتُخزَّن بالذاكرة لحين تحديث قاعدة البيانات."""
    data = cache.get('lookup_data')
    if data:
        return data

    brand_pairs = list(CarSpecification.objects.values('brand_ar', 'brand_en').distinct())
    en_by_ar = {}
    for p in brand_pairs:
        en_by_ar.setdefault(p['brand_ar'], p['brand_en'])
    brand_suggestions = sorted(en_by_ar.keys())
    brand_suggestions_en = [
        {'ar': ar, 'en': en_by_ar.get(ar, '')}
        for ar in brand_suggestions
    ]
    from collections import Counter
    brand_counts = Counter(CarSpecification.objects.values_list('brand_ar', flat=True))
    popular_brands = [
        {'ar': ar, 'en': en_by_ar.get(ar, '')}
        for ar, _ in brand_counts.most_common(12)
    ]
    data = {
        'brand_suggestions': brand_suggestions,
        'brand_suggestions_en': brand_suggestions_en,
        'popular_brands': popular_brands,
    }
    cache.set('lookup_data', data, 3600)
    return data


def _search_context(request):
    """معالجة فلترة البحث وإرجاع الـ context المشترك بين صفحة البحث والقسم المضمّن."""
    brand = request.GET.get('brand', '').strip()
    model = request.GET.get('model', '').strip()
    year = request.GET.get('year', '').strip()
    engine = request.GET.get('engine', '').strip()
    engine_type = request.GET.get('engine_type', '').strip()
    spec_region = request.GET.get('spec_region', '').strip()
    fuel = request.GET.get('fuel', '').strip()

    required, optional = _filters(request)

    cars = None
    if required != Q() or optional:
        qs = CarSpecification.objects.all()
        if optional:
            cars = _apply(qs, required, optional)
        else:
            cars = _apply(qs, required, [])
        cars = cars.order_by(
            'brand_ar', 'model_ar', 'year', 'spec_region',
            'engine_type', 'engine_norm', 'engine', 'id',
        )

    car_groups = _group_search_results(cars, engine, engine_type)

    lookup = _cached_lookup_data()

    return {
        'cars': cars,
        'car_groups': car_groups,
        'brand_suggestions': lookup['brand_suggestions'],
        'brand_suggestions_en': lookup['brand_suggestions_en'],
        'popular_brands': lookup['popular_brands'],
        'engine_type_choices': CarSpecification.ENGINE_TYPE_CHOICES,
        'spec_region_choices': [{'value': v, 'label': l} for v, l in CarSpecification.SPEC_REGION_CHOICES],
        'brand': brand,
        'model': model,
        'year': year,
        'engine': engine,
        'engine_type': engine_type,
        'spec_region': spec_region,
        'fuel': fuel,
        'missing_spec_region': bool(any((brand, model, year, engine, engine_type, fuel)) and not spec_region),
    }


def index_view(request):
    banners = AdBanner.objects.filter(is_active=True).order_by('order', '-created_at')
    gateway_card_ads = {
        ad.gateway_card_target: ad
        for ad in banners.filter(position='gateway_card').exclude(gateway_card_target='')
    }
    gateway_card_fallback = banners.filter(position='gateway_card', gateway_card_target='').first()
    context = {
        'banners': banners,
        'gateway_grid_ad': banners.filter(position='gateway_grid').first(),
        'gateway_search_card_ad': gateway_card_ads.get('search') or gateway_card_fallback,
        'gateway_mix_card_ad': gateway_card_ads.get('mix') or gateway_card_fallback,
        'gateway_dealers_card_ad': gateway_card_ads.get('dealers') or gateway_card_fallback,
        'gateway_maintenance_card_ad': gateway_card_ads.get('maintenance') or gateway_card_fallback,
    }
    return render(request, 'cars/index.html', context)


def legacy_budget_redirect(request):
    return redirect('index', permanent=True)


def search_view(request):
    context = _search_context(request)
    context['banners'] = AdBanner.objects.filter(is_active=True).order_by('order', '-created_at')
    context['has_params'] = bool(
        request.GET.get('brand') or request.GET.get('model') or request.GET.get('year')
        or request.GET.get('engine') or request.GET.get('engine_type')
        or request.GET.get('spec_region') or request.GET.get('fuel')
    )
    return render(request, 'cars/search.html', context)


def dealers_view(request):
    if not SiteSettings.load().show_dealers_card:
        return redirect('index')

    category = request.GET.get('category', 'oil')
    parts_region = request.GET.get('parts_region', 'all')
    if category not in dict(Dealer.DEALER_TYPE_CHOICES):
        category = 'oil'
    if parts_region not in dict(Dealer.PARTS_REGION_CHOICES):
        parts_region = 'all'

    dealers = Dealer.objects.filter(dealer_type=category, is_active=True)
    if category == 'parts' and parts_region != 'all':
        dealers = dealers.filter(Q(parts_region=parts_region) | Q(parts_region='all'))
    dealers = list(dealers)

    dealer_card_fallback = AdBanner.objects.filter(
        is_active=True,
        position='dealer_card',
        target_dealer__isnull=True,
    ).first()
    dealer_ads = {
        ad.target_dealer_id: ad
        for ad in AdBanner.objects.filter(
            is_active=True,
            position='dealer_card',
            target_dealer__in=dealers,
        ).select_related('target_dealer')
    }
    for dealer in dealers:
        dealer.card_ad = dealer_ads.get(dealer.id) or dealer_card_fallback
    return render(request, 'cars/dealers.html', {
        'dealers': dealers,
        'category': category,
        'parts_region': parts_region,
        'dealer_type_choices': Dealer.DEALER_TYPE_CHOICES,
        'parts_region_choices': Dealer.PARTS_REGION_CHOICES,
    })


@require_POST
def track_app_install(request):
    event = request.POST.get('event', '')
    if event not in dict(AppInstallMetric.EVENT_CHOICES):
        return JsonResponse({'success': False}, status=400)
    metric, _ = AppInstallMetric.objects.get_or_create(event=event)
    AppInstallMetric.objects.filter(pk=metric.pk).update(count=F('count') + 1)
    cache.delete('admin_dash_stats')
    return JsonResponse({'success': True})


@require_POST
def track_dealer_click(request, dealer_id, action):
    if action not in dict(DealerClickMetric.ACTION_CHOICES):
        return JsonResponse({'success': False}, status=400)
    dealer = Dealer.objects.filter(pk=dealer_id, is_active=True).first()
    if not dealer:
        return JsonResponse({'success': False}, status=404)
    metric, _ = DealerClickMetric.objects.get_or_create(dealer=dealer, action=action)
    DealerClickMetric.objects.filter(pk=metric.pk).update(count=F('count') + 1)
    cache.delete('admin_dash_stats')
    return JsonResponse({'success': True})


def get_suggestions(request):
    brand = request.GET.get('brand', '').strip()
    model = request.GET.get('model', '').strip()
    year = request.GET.get('year', '').strip()
    engine_type = request.GET.get('engine_type', '').strip()
    spec_region = request.GET.get('spec_region', '').strip()
    engine = request.GET.get('engine', '').strip()

    def base_qs():
        qs = CarSpecification.objects.filter(
            Q(brand_norm__icontains=fold_ar(brand)) | Q(brand_en__icontains=brand),
        )
        if model:
            qs = qs.filter(Q(model_norm__icontains=fold_ar(model)) | Q(model_en__icontains=model))
        return qs

    def narrow(qs):
        if year:
            try:
                qs = qs.filter(year=int(year))
            except ValueError:
                pass
        if engine_type:
            qs = qs.filter(engine_type=engine_type)
        if spec_region:
            qs = qs.filter(spec_region=spec_region)
        if engine:
            qs = qs.filter(engine_norm__icontains=fold_engine(engine))
        return qs

    if brand:
        models_list = list(narrow(base_qs()).values_list('model_ar', 'model_en').distinct().order_by('model_ar')[:400])
        models = [{'ar': m[0], 'en': m[1]} for m in models_list]

        engines = []
        if model and year and spec_region:
            engine_rows = list(
                narrow(base_qs())
                .values('engine', 'engine_code', 'engine_type')
                .distinct()
                .order_by('engine', 'engine_type', 'engine_code')[:400]
            )
            engine_choices = dict(CarSpecification.ENGINE_TYPE_CHOICES)
            engine_details = {}
            for row in engine_rows:
                value = row['engine']
                key = (value, row['engine_type'])
                details = engine_details.setdefault(key, [])
                detail_parts = [engine_choices.get(row['engine_type'], row['engine_type'])]
                if row['engine_code']:
                    detail_parts.append(row['engine_code'])
                detail = ' · '.join(part for part in detail_parts if part)
                if detail and detail not in details:
                    details.append(detail)
            engines = [
                {
                    'value': value,
                    'detail': ' / '.join(details),
                    'engine_type': engine_type_value,
                }
                for (value, engine_type_value), details in engine_details.items()
            ]

        return JsonResponse({'models': models, 'engines': engines})

    return JsonResponse({'models': [], 'engines': []})


def is_staff_user(user):
    return user.is_authenticated and user.is_staff



MIX_CAR_LIMIT = 3000


def _mix_cars():
    """قائمة السيارات لحاسبة الخلط — مقصودة عمداً بحد أقصى (أحدث/أشهر أولاً).

    القائمة الكاملة ضخمة وقد تتضخم؛ يبقى باقي السيارات في قاعدة البيانات
    وتصل إليه عبر البحث أو لوحة الإدارة. لا تُحمَّل كل الصفوف في الذاكرة.
    """
    return (CarSpecification.objects.all()
            .order_by('-year', 'brand_ar', 'model_ar')
            .only(
                'id', 'brand_ar', 'model_ar', 'year', 'spec_region', 'engine',
                'engine_code', 'engine_type', 'octane', 'tank'
            )[:MIX_CAR_LIMIT])


def _octane_number(value):
    match = re.search(r'\d+(?:\.\d+)?', str(value or ''))
    return match.group(0) if match else ''


def _format_iqd(value):
    try:
        return f'{int(round(float(value))):,}'
    except (TypeError, ValueError):
        return ''


def _mix_car_options():
    options = []
    for car in _mix_cars():
        octane_value = _octane_number(car.octane)
        if not octane_value:
            continue
        engine_parts = [car.engine]
        if car.engine_code:
            engine_parts.append(car.engine_code)
        options.append({
            'id': car.id,
            'brand': car.brand_ar,
            'model': car.model_ar,
            'year': car.year,
            'spec_region': car.spec_region,
            'spec_region_label': car.get_spec_region_display(),
            'engine': ' · '.join(part for part in engine_parts if part),
            'engine_type': car.get_engine_type_display() if car.engine_type else '',
            'octane': octane_value,
            'octane_label': str(car.octane or ''),
            'tank': str(car.tank) if car.tank else '',
        })
    return options


def _mix_calculator_context(result=None):
    settings = SiteSettings.load()
    return {
        'car_options': _mix_car_options(),
        'result': result,
        'regular_fuel_price_iqd': settings.regular_fuel_price_iqd,
        'premium_fuel_price_iqd': settings.premium_fuel_price_iqd,
        'regular_fuel_price_iqd_display': _format_iqd(settings.regular_fuel_price_iqd),
        'premium_fuel_price_iqd_display': _format_iqd(settings.premium_fuel_price_iqd),
    }


def mix_calculator_view(request):
    result = None
    
    if request.method == 'POST':
        try:
            target = float(request.POST.get('octane_target'))
            o1 = float(request.POST.get('octane1'))
            o2 = float(request.POST.get('octane2'))
            tank = float(request.POST.get('tank_capacity'))
            
            if tank <= 0:
                messages.error(request, "⚠️ سعة الخزان يجب أن تكون أكبر من صفر")
                return render(request, 'cars/mix_calculator.html', _mix_calculator_context(result))
            
            if o1 < 80 or o1 > 120 or o2 < 80 or o2 > 120:
                messages.error(request, "⚠️ رقم الأوكتان يجب أن يكون بين 80 و 120")
                return render(request, 'cars/mix_calculator.html', _mix_calculator_context(result))
            
            if not (min(o1, o2) <= target <= max(o1, o2)):
                messages.error(request, "⚠️ الأوكتان المطلوب يجب أن يكون بين النوعين")
            else:
                if o1 != o2:
                    r1 = (target - o2) / (o1 - o2)
                else:
                    r1 = 0.5
                r2 = 1 - r1
                amount1 = round(r1 * tank, 2)
                amount2 = round(r2 * tank, 2)
                settings = SiteSettings.load()
                regular_price = settings.regular_fuel_price_iqd or 0
                premium_price = settings.premium_fuel_price_iqd or 0
                regular_cost = round(amount1 * regular_price)
                premium_cost = round(amount2 * premium_price)
                total_cost = round((amount1 * regular_price) + (amount2 * premium_price))
                result = {
                    'octane1': o1,
                    'octane2': o2,
                    'amount1': amount1,
                    'amount2': amount2,
                    'percent1': round(r1 * 100, 2),
                    'percent2': round(r2 * 100, 2),
                    'target': target,
                    'tank': tank,
                    'regular_price': regular_price,
                    'premium_price': premium_price,
                    'regular_cost': regular_cost,
                    'premium_cost': premium_cost,
                    'total_cost': total_cost,
                    'regular_cost_display': _format_iqd(regular_cost),
                    'premium_cost_display': _format_iqd(premium_cost),
                    'total_cost_display': _format_iqd(total_cost),
                    'show_cost': regular_price > 0 and premium_price > 0,
                }
                messages.success(request, "✅ تم حساب الخلطة بنجاح!")
        except ValueError:
            messages.error(request, "⚠️ يرجى إدخال أرقام صحيحة.")
        except ZeroDivisionError:
            messages.error(request, "⚠️ حدث خطأ في الحساب. تأكد من القيم المدخلة.")
    
    return render(request, 'cars/mix_calculator.html', _mix_calculator_context(result))


def recommendations_view(request, car_id):
    try:
        car = CarSpecification.objects.get(id=car_id)
    except CarSpecification.DoesNotExist:
        messages.error(request, "\u26a0\ufe0f \u0627\u0644\u0633\u064a\u0627\u0631\u0629 \u063a\u064a\u0631 \u0645\u0648\u062c\u0648\u062f\u0629")
        return redirect('index')
    return render(request, 'cars/recommendations.html', {
        'car': car,
        'display_recommendations': _unique_recommendation_lines(car.recommendations),
    })


def _unique_recommendation_lines(text):
    if not text:
        return ''
    lines = []
    seen = set()
    for raw_line in str(text).replace('؛', '\n').splitlines():
        line = raw_line.strip(" \t\r\n-•*،,.؛")
        key = ' '.join(line.split()).lower()
        if line and key not in seen and not _is_repeated_spec_line(key):
            seen.add(key)
            lines.append(line)
    return '\n'.join(lines)


def _is_repeated_spec_line(normalized_line):
    repeated_fields = (
        'السنة', 'سنة الصنع', 'year',
        'المحرك', 'سعة المحرك', 'كود المحرك', 'engine', 'engine code',
        'نوع الوقود', 'الوقود', 'fuel',
        'الأوكتان', 'اوكتان', 'رقم الأوكتان', 'رقم اوكتان', 'octane',
        'لزوجة الزيت', 'زيت المحرك', 'oil viscosity', 'oil visc',
        'سعة الزيت', 'سعة زيت المحرك', 'oil capacity',
        'ماركات الزيت', 'ماركة الزيت', 'oil brands',
    )
    separators = (':', '：', '-', '–', '—', '=')
    return any(
        normalized_line == field or
        any(normalized_line.startswith(field + sep) for sep in separators) or
        any(normalized_line.startswith(field + ' ' + sep) for sep in separators)
        for field in repeated_fields
    )


def privacy_view(request):
    return render(request, 'cars/privacy.html')


def about_view(request):
    return render(request, 'cars/about.html')


def ads_txt_view(request):
    settings_obj = SiteSettings.load()
    content = settings_obj.ads_txt.strip() or "# ads.txt - populated after Google AdSense approval"
    return HttpResponse(content, content_type='text/plain; charset=utf-8')


def robots_view(request):
    base = request.build_absolute_uri('/').rstrip('/')
    text = (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
    return HttpResponse(text, content_type='text/plain; charset=utf-8')


def sitemap_view(request):
    from django.urls import reverse
    from django.utils import timezone
    from django.utils.html import escape

    root_url = request.build_absolute_uri('/')
    host = root_url.rstrip('/')
    today = timezone.localdate().isoformat()
    settings_obj = SiteSettings.load()

    urls = [
        {'loc': root_url, 'priority': '1.0', 'freq': 'daily'},
        {'loc': host + reverse('search'), 'priority': '0.9', 'freq': 'daily'},
        {'loc': host + reverse('mix_calculator'), 'priority': '0.8', 'freq': 'weekly'},
        {'loc': host + reverse('about'), 'priority': '0.5', 'freq': 'monthly'},
        {'loc': host + reverse('privacy'), 'priority': '0.3', 'freq': 'yearly'},
    ]
    if settings_obj.show_dealers_card:
        urls.append({'loc': host + reverse('dealers'), 'priority': '0.8', 'freq': 'weekly'})
    if settings_obj.show_maintenance_card:
        urls.append({'loc': host + reverse('maintenance'), 'priority': '0.8', 'freq': 'weekly'})
        for slug in CarSymptom.objects.filter(is_active=True).values_list('slug', flat=True)[:1000]:
            urls.append({'loc': host + reverse('symptom_detail', args=[slug]), 'priority': '0.6', 'freq': 'monthly'})

    chunk = '\n'.join(
        f"   <url><loc>{escape(u['loc'])}</loc><lastmod>{today}</lastmod>"
        f"<changefreq>{u['freq']}</changefreq><priority>{u['priority']}</priority></url>"
        for u in urls
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + chunk
        + '\n</urlset>\n'
    )
    return HttpResponse(xml, content_type='application/xml; charset=utf-8')


def _new_code(sponsor):
    """يولّد كوداً فريداً (بادئة + أرقام) غير موجود مسبقاً في القاعدة.

    يُفحص التفرد عالمياً (code فريد في جدول PromoCode) وليس بين أكواد
    الشركة فقط، حتى لا يصطدم كودا شركتين لهما نفس البادئة فيسبب خطأ 500.
    يُستعمل استعلام وجود مفهرس بدل تحميل كل الأكواد في الذاكرة — مهم مع
    تراكم الأكواد.
    """
    import secrets

    prefix = (sponsor.code_prefix or '').strip().upper()
    if not prefix:
        prefix = ''.join(ch.strip() for ch in getattr(sponsor, 'slug', '') or '' if ch.isalnum())[:6].upper()
    if not prefix:
        prefix = 'CODE'

    # الكود فريد عالمياً (unique=True) لذا نفحص كل الصفوف، لا صفوف الشركة فقط.
    def _exists(code):
        return PromoCode.objects.filter(code=code).exists()

    for _ in range(40):
        code = f"{prefix}-{1000 + secrets.randbelow(9000)}"
        if not _exists(code):
            return code
    # احتياط: أرقام أوسع للتقليل من فرص التصادم تحت بادئة مشتركة
    for _ in range(80):
        code = f"{prefix}-{100000 + secrets.randbelow(900000)}"
        if not _exists(code):
            return code
    return None


def generate_promo_code(request):
    """يولّد كود خصم فريداً لزائر لدى شركة راعية (يُستدعى من زر «احصل على خصم»).

    POST: sponsor=<slug>
    يعيد JSON: { success, code, discount, sponsor, status }
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST only'}, status=405)
    slug = request.POST.get('sponsor', '').strip() or request.GET.get('sponsor', '').strip()
    sponsor = Sponsor.objects.filter(slug=slug, is_active=True).first()
    if not sponsor:
        return JsonResponse({'success': False, 'error': 'شركة غير موجودة أو غير مفعلة'}, status=404)

    ip = _client_ip(request)
    shared = caches['shared']
    visitor_key = f'promo:visitor:{sponsor.pk}:{ip}'
    existing_code = shared.get(visitor_key)
    if existing_code:
        existing = PromoCode.objects.filter(code=existing_code, sponsor=sponsor, status='active').first()
        if existing:
            return JsonResponse({
                'success': True,
                'code': existing.code,
                'discount': sponsor.discount,
                'sponsor': sponsor.name,
                'status': 'existing',
            })

    # حدّ توليد حقيقي لكل عنوان IP في الساعة — لا يحسب إعادة عرض الكود القديم.
    rate_key = 'codegen:' + ip
    generated = shared.get(rate_key, 0)
    if generated >= CODE_GEN_RATE_LIMIT:
        return JsonResponse({'success': False, 'error': 'حاول مرة أخرى لاحقاً'}, status=429)

    active_count = PromoCode.objects.filter(sponsor=sponsor, status='active').count()
    if active_count >= 500:
        return JsonResponse({'success': False, 'error': 'عدد الأكواد النشطة للشركة وصل الحد الأقصى'}, status=429)

    # حماية من سباق التوافق: بين فحص وجود الكود وإدراجه قد يتفرّغ طلب آخر
    # لنفس الكود (خاصة عند بادئة مشتركة). نعيد المحاولة بكود جديد بدل خطأ 500.
    from django.db import IntegrityError
    code = None
    for _ in range(10):
        candidate = _new_code(sponsor)
        if not candidate:
            break
        try:
            PromoCode.objects.create(code=candidate, sponsor=sponsor, status='active')
            code = candidate
            break
        except IntegrityError:
            continue  # تصادم (تسابق) — جرّب كوداً آخر

    if not code:
        return JsonResponse({'success': False, 'error': 'تعذر توليد كود الآن'}, status=500)

    shared.set(rate_key, generated + 1, 3600)
    shared.set(visitor_key, code, PROMO_CODE_IP_CACHE_TTL)

    return JsonResponse({
        'success': True,
        'code': code,
        'discount': sponsor.discount,
        'sponsor': sponsor.name,
        'status': 'active',
    })


def verify_code_page(request, slug):
    """صفحة تحقق خاصة بموظف الشركة: تُدخل الكود ليتأكد أنه حقيقي وساري.

    المسار: /verify/<slug>/  — مثال زيت الحسام: /verify/hisam/
    """
    sponsor = Sponsor.objects.filter(slug=slug, is_active=True).first()
    if not sponsor:
        return render(request, 'cars/code_verify.html', {'sponsor': None})
    current = _current_sponsor(request)
    if not current or current.id != sponsor.id:
        login_url = reverse('services_login') + '?next=' + request.path
        return redirect(login_url)

    result = None
    code_input = request.POST.get('code', '').strip().upper()
    if request.method == 'POST' and code_input:
        promo = PromoCode.objects.filter(code=code_input, sponsor=sponsor).first()
        if not promo:
            result = {'status': 'invalid', 'message': 'الكود غير صحيح — تأكد من الكتابة وأعد المحاولة.'}
        elif promo.status == 'used':
            result = {'status': 'used', 'message': 'هذا الكود مستخدم مسبقاً ولا يصلح للخصم مرة أخرى.', 'code': promo.code}
        else:
            from django.utils import timezone
            promo.status = 'used'
            promo.used_at = timezone.now()
            promo.verified_by = sponsor.name
            promo.save(update_fields=['status', 'used_at', 'verified_by'])
            result = {'status': 'valid', 'message': 'الكود صحيح وساري — الخصم مفعّل.', 'code': promo.code, 'discount': sponsor.discount}

    return render(request, 'cars/code_verify.html', {
        'sponsor': sponsor,
        'result': result,
    })


def _client_ip(request):
    """عنوان الزائر الحقيقي خلف nginx دون قدرة الزائر على تزويره.

    nginx يُلحق عنوانه الحقيقي ($remote_addr) آخر X-Forwarded-For؛ أول قيمة
    يرسلها الزائر نفسه فيمكن تزويرها، لذا نأخذ القيمة الأخيرة دائماً.
    """
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.rsplit(',')[-1].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


def _rate_limit(request, prefix, limit, window_seconds):
    shared = caches['shared']
    key = f'{prefix}:{_client_ip(request)}'
    used = shared.get(key, 0)
    if used >= limit:
        return False
    shared.set(key, used + 1, window_seconds)
    return True


def services_login(request):
    """صفحة «نافذة الخدمات» — تسجيل دخول موحّد للرعاة/المعلنين.

    يدخل بها من يملك حساباً (راعي) ليرى قسمه ويتحقق من الأكواد.
    """
    next_url = request.GET.get('next') or reverse('services_dashboard')
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = reverse('services_dashboard')
    error = None

    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        password = request.POST.get('password', '')
        client_ip = _client_ip(request)

        fail_key = 'sfail:' + client_ip
        failures = caches['shared'].get(fail_key, 0)
        if failures >= 5:
            error = 'تم حظر الدخول مؤقتاً بسبب محاولات كثيرة — حاول بعد قليل.'
        else:
            sponsor = (Sponsor.objects.filter(slug=identifier, is_active=True).first()
                       or Sponsor.objects.filter(name=identifier, is_active=True).first())
            if sponsor and sponsor.password and sponsor.check_password(password):
                caches['shared'].delete(fail_key)
                request.session.flush()
                request.session['sponsor_id'] = sponsor.id
                request.session['sponsor_name'] = sponsor.name
                request.session['sponsor_slug'] = sponsor.slug
                return redirect(next_url)
            caches['shared'].set(fail_key, failures + 1, 300)
            error = 'بيانات الدخول غير صحيحة — تأكد من اسم الحساب وكلمة المرور.'

    return render(request, 'cars/services.html', {
        'mode': 'login',
        'error': error,
    })


def _current_sponsor(request):
    sponsor_id = request.session.get('sponsor_id')
    if not sponsor_id:
        return None
    return Sponsor.objects.filter(id=sponsor_id, is_active=True).first()


def services_dashboard(request):
    """لوحة الراعي داخل نافذة الخدمات (تتطلب تسجيل الدخول)."""
    sponsor = _current_sponsor(request)
    if not sponsor:
        return redirect('services_login')

    result = None
    code_input = request.POST.get('code', '').strip().upper()
    if request.method == 'POST' and code_input:
        promo = PromoCode.objects.filter(code=code_input, sponsor=sponsor).first()
        if not promo:
            result = {'status': 'invalid', 'message': 'الكود غير صحيح — تأكد من الكتابة وأعد المحاولة.'}
        elif promo.status == 'used':
            result = {'status': 'used', 'message': 'هذا الكود مستخدم مسبقاً ولا يصلح للخصم مرة أخرى.', 'code': promo.code}
        else:
            from django.utils import timezone
            promo.status = 'used'
            promo.used_at = timezone.now()
            promo.verified_by = sponsor.name
            promo.save(update_fields=['status', 'used_at', 'verified_by'])
            result = {'status': 'valid', 'message': 'الكود صحيح وساري — الخصم مفعّل.', 'code': promo.code, 'discount': sponsor.discount}

    total_codes = PromoCode.objects.filter(sponsor=sponsor).count()
    used_codes = PromoCode.objects.filter(sponsor=sponsor, status='used').count()

    return render(request, 'cars/services.html', {
        'mode': 'dashboard',
        'sponsor': sponsor,
        'result': result,
        'total_codes': total_codes,
        'used_codes': used_codes,
    })


@require_POST
def services_logout(request):
    request.session.flush()
    return redirect('services_login')


_REPORT_PERIODS = (
    ('all', 'الكل'),
    ('day', 'يوم'),
    ('month', 'شهر'),
    ('year', 'سنة'),
)

# حد أقصى للصفوف المحمّلة/المعروضة في التقرير دفعة واحدة؛ البقية تبقى في قاعدة البيانات
_REPORT_LIMIT = 500

# حد توليد أكواد لكل عنوان IP في الساعة (حماية من التخزين الآلي)
CODE_GEN_RATE_LIMIT = 60
PROMO_CODE_IP_CACHE_TTL = 60 * 60 * 24 * 2


@staff_member_required
def admin_cars_report(request):
    """تقرير إداري بسيط يلخص السيارات حسب الماركة والموديل."""
    brands_qs = (
        CarSpecification.objects
        .values('brand_ar', 'brand_en')
        .annotate(total_cars=Count('id'), total_models=Count('model_ar', distinct=True))
        .order_by('brand_ar')
    )
    model_rows = (
        CarSpecification.objects
        .values('brand_ar', 'model_ar', 'model_en')
        .annotate(total=Count('id'))
        .order_by('brand_ar', 'model_ar')
    )

    models_by_brand = {}
    for row in model_rows:
        models_by_brand.setdefault(row['brand_ar'], []).append(row)

    brands = []
    for brand in brands_qs:
        item = dict(brand)
        item['models'] = models_by_brand.get(item['brand_ar'], [])
        brands.append(item)

    total_cars = CarSpecification.objects.count()
    total_brands = len(brands)
    total_models = CarSpecification.objects.values('brand_ar', 'model_ar').distinct().count()

    if request.GET.get('download') == '1':
        lines = [
            '=' * 60,
            'تقرير السيارات — سيارتي',
            '=' * 60,
            f'إجمالي السيارات: {total_cars}',
            f'إجمالي الماركات: {total_brands}',
            f'إجمالي الموديلات: {total_models}',
            '-' * 60,
        ]
        for brand in brands:
            title = brand['brand_ar']
            if brand.get('brand_en'):
                title += f" ({brand['brand_en']})"
            lines.append(f"\n{title}: {brand['total_cars']} سيارة | {brand['total_models']} موديل")
            for model in brand['models']:
                model_name = model['model_ar'] or model['model_en'] or 'غير محدد'
                if model.get('model_en') and model['model_en'] != model_name:
                    model_name += f" ({model['model_en']})"
                lines.append(f"  - {model_name}: {model['total']} سيارة")
        response = HttpResponse('\n'.join(lines), content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="cars_report.txt"'
        return response

    return render(request, 'admin/cars_report.html', {
        'brands': brands,
        'total_cars': total_cars,
        'total_brands': total_brands,
        'total_models': total_models,
    })


@staff_member_required
def admin_codes_report(request):
    """تقرير أكواد الخصم لجهة الطباعة/التصدير النصي (للمدير فقط).

    فلترة اليوم/الشهر/السنة، يعرض كل أكواد الخصم ضمن النطاق، وينزل ملف
    نصي (txt) مرتباً بنفس التفاصيل عبر ?download=1.
    """
    from datetime import date
    today = date.today()

    period = request.GET.get('period', 'month')
    if period not in ('all', 'day', 'month', 'year'):
        period = 'month'

    def _valid_int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    qs = PromoCode.objects.select_related('sponsor').order_by('-created_at')

    if period == 'day':
        day = request.GET.get('day')
        if not day:
            day = today.isoformat()
        try:
            day_filter = date.fromisoformat(day)
        except ValueError:
            day_filter = today
        qs = qs.filter(created_at__date=day_filter)
    elif period == 'month':
        month = request.GET.get('month')
        if not month:
            month = today.strftime('%Y-%m')
        y, _, m = month.partition('-')
        qs = qs.filter(
            created_at__year=_valid_int(y, today.year),
            created_at__month=_valid_int(m, today.month),
        )
    elif period == 'year':
        year = request.GET.get('year')
        if not year:
            year = str(today.year)
        qs = qs.filter(created_at__year=_valid_int(year, today.year))

    # إجمالي صحيح من قاعدة البيانات والصفوف المقصوصة فقط تُحمَّل في الذاكرة
    total = qs.count()
    used = qs.filter(status='used').count()
    rows = list(qs[:_REPORT_LIMIT])

    if period == 'day':
        sel = request.GET.get('day') or today.isoformat()
    elif period == 'month':
        sel = request.GET.get('month') or today.strftime('%Y-%m')
    elif period == 'year':
        sel = request.GET.get('year') or str(today.year)
    else:
        sel = 'الكل'
    period_label = dict(_REPORT_PERIODS).get(period, 'الكل')

    def _lines():
        lines = []
        lines.append('=' * 50)
        lines.append('تقرير أكواد الخصم — سيارتي')
        lines.append('=' * 50)
        lines.append(f'الفترة: {period_label} | {sel}')
        lines.append(f'عدد الأكواد: {total} | المستخدمة: {used}')
        lines.append('-' * 50)
        lines.append('الكود\tالشركة\tالحالة\tتاريخ التوليد\tتاريخ الاستخدام\tتم التحقق من قبل')
        lines.append('-' * 50)
        status_map = {'active': 'نشط', 'used': 'مستخدم'}
        for r in rows:
            lines.append(
                '\t'.join([
                    r.code,
                    r.sponsor.name,
                    status_map.get(r.status, r.status),
                    r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else '',
                    r.used_at.strftime('%Y-%m-%d %H:%M') if r.used_at else '',
                    r.verified_by or '—',
                ])
            )
        lines.append('=' * 50)
        return '\n'.join(lines)

    if request.GET.get('download') == '1':
        filename = f"promo_codes_{period}_{sel}.txt" if period != 'all' else "promo_codes_all.txt"
        text = _lines()
        response = HttpResponse(text, content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    return render(request, 'admin/codes_report.html', {
        'periods': _REPORT_PERIODS,
        'period': period,
        'rows': rows,
        'total': total,
        'used': used,
    })
