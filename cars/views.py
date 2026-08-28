import pandas as pd
from pathlib import Path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponse
from django import forms
from .models import CarSpecification, AdBanner, FeatureCard, SiteSettings
from .services.excel_importer import import_cars_from_excel
from .services.textnorm import fold_ar, fold_engine


SW_FILE = Path(__file__).resolve().parent / 'static' / 'shared' / 'sw.js'


def manifest_view(request):
    manifest = {
        "name": "سيارتي - دليل مواصفات السيارات الذكي",
        "short_name": "سيارتي",
        "description": "دليل مواصفات السيارات - مواصفات، زيوت، إطارات، وتوصيات لكل سيارة.",
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


class CsvImportForm(forms.Form):
    excel_file = forms.FileField(label="Ø§Ø®ØªØ± Ù…Ù„Ù Ø§Ù„Ø£ÙƒØ³Ù„")


RELAX_LABELS = {
    'spec_region': 'مواصفات المنطقة',
    'engine_type': 'نوع المحرك',
    'year': 'سنة الصنع',
    'engine': 'سعة المحرك',
    'fuel': 'نوع الوقود',
}


def _filters(request):
    """بناء فلاتر البحث من المعاملات مع التطبيع، ويعيد قائمة (مفتاح, Q).

    المرشحات النصية (الماركة/الموديل/المحرك) تطابق على حقول *_norm
    الموحّدة، وأي قيد إضافي (منطقة/نوع/سنة/محرك) قيد قابل للتفكيك حتى
    نتمكن لاحقاً من "البحث المتساهل".
    """
    brand = request.GET.get('brand', '').strip()
    model = request.GET.get('model', '').strip()
    year = request.GET.get('year', '').strip()
    engine = request.GET.get('engine', '').strip()
    engine_type = request.GET.get('engine_type', '').strip()
    spec_region = request.GET.get('spec_region', '').strip()
    fuel = request.GET.get('fuel', '').strip()

    required = Q()
    if brand:
        b = fold_ar(brand)
        required &= Q(brand_norm__icontains=b) | Q(brand_en__icontains=brand)
    if model:
        m = fold_ar(model)
        required &= Q(model_norm__icontains=m) | Q(model_en__icontains=model)

    optional = []  # (key, Q) — قابلة للإسقاط في البحث المتساهل
    if year:
        try:
            optional.append(('year', Q(year=int(year))))
        except ValueError:
            optional.append(('year', Q(year__icontains=year)))
    if engine_type:
        optional.append(('engine_type', Q(engine_type__icontains=engine_type)))
    if spec_region:
        optional.append(('spec_region', Q(spec_region__icontains=spec_region)))
    if fuel:
        f = fold_ar(fuel)
        optional.append(('fuel', Q(fuel__icontains=f)))
    if engine:
        e = fold_engine(engine)
        optional.append(('engine', Q(engine_norm__icontains=e)))

    return required, optional


def _apply(qs, required, keep_keys):
    q = required
    for key, cond in keep_keys:
        q &= cond
    if q == Q():
        return qs.none()
    return qs.filter(q)


def index_view(request):
    brand = request.GET.get('brand', '').strip()
    model = request.GET.get('model', '').strip()
    year = request.GET.get('year', '').strip()
    engine = request.GET.get('engine', '').strip()
    engine_type = request.GET.get('engine_type', '').strip()
    spec_region = request.GET.get('spec_region', '').strip()
    fuel = request.GET.get('fuel', '').strip()

    required, optional = _filters(request)

    cars = None
    relaxed = []
    if required != Q() or optional:
        qs = CarSpecification.objects.all()
        if optional:
            cars = _apply(qs, required, optional)
            if not cars.exists() and required != Q():
                # البحث المتساهل: نسقط القيود الأقل أهمية حتى تظهر النتائج
                keep = list(optional)
                while keep and not cars.exists():
                    dropped = keep.pop()
                    relaxed.append(dropped[0])
                    cars = _apply(qs, required, keep)
            if not cars or not cars.exists():
                cars = _apply(qs, required, [])
        else:
            cars = _apply(qs, required, [])
        if cars is not None and not cars.exists():
            cars = None
    else:
        cars = None

    banners = AdBanner.objects.filter(is_active=True).order_by('order', '-created_at')

    feature_cards = FeatureCard.objects.filter(is_active=True).order_by('order', 'created_at')

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

    engine_type_choices = CarSpecification.ENGINE_TYPE_CHOICES
    spec_region_choices = CarSpecification.SPEC_REGION_CHOICES
    spec_region_display = [{'value': v, 'label': l} for v, l in spec_region_choices]

    context = {
        'cars': cars,
        'banners': banners,
        'feature_cards': feature_cards,
        'brand_suggestions': brand_suggestions,
        'brand_suggestions_en': brand_suggestions_en,
        'popular_brands': popular_brands,
        'engine_type_choices': engine_type_choices,
        'spec_region_choices': spec_region_display,
        'brand': brand,
        'model': model,
        'year': year,
        'engine': engine,
        'engine_type': engine_type,
        'spec_region': spec_region,
        'fuel': fuel,
        'relaxed': [RELAX_LABELS.get(k, k) for k in relaxed],
    }
    return render(request, 'cars/index.html', context)


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
        if model:
            engines_raw = list(narrow(base_qs()).values_list('engine', flat=True).distinct().order_by('engine')[:200])
            engines = engines_raw
        return JsonResponse({'models': models, 'engines': engines})

    return JsonResponse({'models': [], 'engines': []})


def is_staff_user(user):
    """Allow only authenticated staff users."""
    return user.is_authenticated and user.is_staff


@login_required
@user_passes_test(is_staff_user)
def import_excel_view(request):
    """
    Excel import endpoint - staff only (validation happens inside the importer).
    """
    form = CsvImportForm()

    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        try:
            result = import_cars_from_excel(excel_file)
            
            if result['success']:
                success_msg = f"âœ… ØªÙ… Ø§Ù„Ø§Ø³ØªÙŠØ±Ø§Ø¯ Ø¨Ù†Ø¬Ø§Ø­! Ø¥Ø¶Ø§ÙØ© {result['created']} ÙˆØªØ­Ø¯ÙŠØ« {result['updated']}."
                if result['failed'] > 0:
                    success_msg += f" âŒ ÙØ´Ù„ {result['failed']} ØµÙ."
                    for failed_row in result['failed_rows'][:5]:
                        messages.warning(request, f"Ø§Ù„ØµÙ {failed_row['row_number']}: {failed_row['error']}")
                messages.success(request, success_msg)
            else:
                for error in result['errors']:
                    messages.error(request, f"âŒ {error}")
                    
        except Exception:
            import logging
            logging.getLogger('cars').exception('Excel import failed')
            messages.error(request, "âš ï¸ Ø­Ø¯Ø« Ø®Ø·Ø£ Ø£Ø«Ù†Ø§Ø¡ Ù…Ø¹Ø§Ù„Ø¬Ø© Ø§Ù„Ù…Ù„Ù. ØªØ£ÙƒØ¯ Ù…Ù† Ø§Ù„ØµÙŠØºØ© ÙˆØ­Ø§ÙˆÙ„ Ù…Ø¬Ø¯Ø¯Ø§Ù‹.")
        
        return redirect('import_excel')

    return render(request, 'cars/import_excel.html', {'form': form})


def mix_calculator_view(request):
    result = None
    
    if request.method == 'POST':
        try:
            target = float(request.POST.get('octane_target'))
            o1 = float(request.POST.get('octane1'))
            o2 = float(request.POST.get('octane2'))
            tank = float(request.POST.get('tank_capacity'))
            
            if tank <= 0:
                messages.error(request, "âš ï¸ Ø³Ø¹Ø© Ø§Ù„Ø®Ø²Ø§Ù† ÙŠØ¬Ø¨ Ø£Ù† ØªÙƒÙˆÙ† Ø£ÙƒØ¨Ø± Ù…Ù† ØµÙØ±")
                return render(request, 'cars/mix_calculator.html', {'cars': CarSpecification.objects.all().order_by('brand_ar', 'model_ar'), 'result': result})
            
            if o1 < 80 or o1 > 120 or o2 < 80 or o2 > 120:
                messages.error(request, "âš ï¸ Ø±Ù‚Ù… Ø§Ù„Ø£ÙˆÙƒØªØ§Ù† ÙŠØ¬Ø¨ Ø£Ù† ÙŠÙƒÙˆÙ† Ø¨ÙŠÙ† 80 Ùˆ 120")
                return render(request, 'cars/mix_calculator.html', {'cars': CarSpecification.objects.all().order_by('brand_ar', 'model_ar'), 'result': result})
            
            if not (min(o1, o2) <= target <= max(o1, o2)):
                messages.error(request, "âš ï¸ Ø§Ù„Ø£ÙˆÙƒØªØ§Ù† Ø§Ù„Ù…Ø·Ù„ÙˆØ¨ ÙŠØ¬Ø¨ Ø£Ù† ÙŠÙƒÙˆÙ† Ø¨ÙŠÙ† Ø§Ù„Ù†ÙˆØ¹ÙŠÙ†")
            else:
                if o1 != o2:
                    r1 = (target - o2) / (o1 - o2)
                else:
                    r1 = 0.5
                r2 = 1 - r1
                result = {
                    'octane1': o1,
                    'octane2': o2,
                    'amount1': round(r1 * tank, 2),
                    'amount2': round(r2 * tank, 2),
                    'percent1': round(r1 * 100, 2),
                    'percent2': round(r2 * 100, 2),
                    'target': target,
                    'tank': tank,
                }
                messages.success(request, "âœ… ØªÙ… Ø­Ø³Ø§Ø¨ Ø§Ù„Ø®Ù„Ø·Ø© Ø¨Ù†Ø¬Ø§Ø­!")
        except ValueError:
            messages.error(request, "âš ï¸ ÙŠØ±Ø¬Ù‰ Ø¥Ø¯Ø®Ø§Ù„ Ø£Ø±Ù‚Ø§Ù… ØµØ­ÙŠØ­Ø©.")
        except ZeroDivisionError:
            messages.error(request, "âš ï¸ Ø­Ø¯Ø« Ø®Ø·Ø£ ÙÙŠ Ø§Ù„Ø­Ø³Ø§Ø¨. ØªØ£ÙƒØ¯ Ù…Ù† Ø§Ù„Ù‚ÙŠÙ… Ø§Ù„Ù…Ø¯Ø®Ù„Ø©.")
    
    cars = CarSpecification.objects.all().only('id', 'brand_ar', 'model_ar', 'year', 'octane', 'oil_capacity').order_by('brand_ar', 'model_ar')
    return render(request, 'cars/mix_calculator.html', {'cars': cars, 'result': result})


def recommendations_view(request, car_id):
    try:
        car = CarSpecification.objects.get(id=car_id)
    except CarSpecification.DoesNotExist:
        messages.error(request, "âš ï¸ Ø§Ù„Ø³ÙŠØ§Ø±Ø© ØºÙŠØ± Ù…ÙˆØ¬ÙˆØ¯Ø©")
        return redirect('index')
    return render(request, 'cars/recommendations.html', {'car': car})


def privacy_view(request):
    return render(request, 'cars/privacy.html')


def about_view(request):
    return render(request, 'cars/about.html')


def ads_txt_view(request):
    from django.http import HttpResponse
    settings_obj = SiteSettings.load()
    content = settings_obj.ads_txt.strip() or "# ads.txt - populated after Google AdSense approval"
    return HttpResponse(content, content_type='text/plain; charset=utf-8')
