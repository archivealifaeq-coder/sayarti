import pandas as pd
from pathlib import Path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponse
from django import forms
from django.core.cache import cache
from .models import CarSpecification, AdBanner, FeatureCard, SiteSettings
from .services.excel_importer import import_cars_from_excel
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
    excel_file = forms.FileField(label="\u0627\u062e\u062a\u0631 \u0645\u0644\u0641 \u0627\u0644\u0623\u0643\u0633\u0644")


RELAX_LABELS = {
    'spec_region': '\u0645\u0648\u0627\u0635\u0641\u0627\u062a \u0627\u0644\u0645\u0646\u0637\u0642\u0629',
    'engine_type': '\u0646\u0648\u0639 \u0627\u0644\u0645\u062d\u0631\u0643',
    'year': '\u0633\u0646\u0629 \u0627\u0644\u0635\u0646\u0639',
    'engine': '\u0633\u0639\u0629 \u0627\u0644\u0645\u062d\u0631\u0643',
    'fuel': '\u0646\u0648\u0639 \u0627\u0644\u0648\u0642\u0648\u062f',
    'trim': '\u0627\u0644\u0641\u0626\u0629',
}


def _filters(request):
    brand = request.GET.get('brand', '').strip()
    model = request.GET.get('model', '').strip()
    year = request.GET.get('year', '').strip()
    engine = request.GET.get('engine', '').strip()
    engine_type = request.GET.get('engine_type', '').strip()
    spec_region = request.GET.get('spec_region', '').strip()
    fuel = request.GET.get('fuel', '').strip()
    trim = request.GET.get('trim', '').strip()

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
            required &= Q(year__icontains=year)

    optional = []
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
    if trim:
        optional.append(('trim', Q(trim__icontains=trim)))

    return required, optional


def _apply(qs, required, keep_keys):
    q = required
    for key, cond in keep_keys:
        q &= cond
    if q == Q():
        return qs.none()
    return qs.filter(q)


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
    trim_choices = list(
        CarSpecification.objects
        .exclude(trim__isnull=True)
        .exclude(trim='')
        .values_list('trim', flat=True)
        .distinct()
        .order_by('trim')[:300]
    )

    data = {
        'brand_suggestions': brand_suggestions,
        'brand_suggestions_en': brand_suggestions_en,
        'popular_brands': popular_brands,
        'trim_choices': trim_choices,
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
    trim = request.GET.get('trim', '').strip()

    required, optional = _filters(request)

    cars = None
    if required != Q() or optional:
        qs = CarSpecification.objects.all()
        if optional:
            cars = _apply(qs, required, optional)
        else:
            cars = _apply(qs, required, [])

    lookup = _cached_lookup_data()

    return {
        'cars': cars,
        'brand_suggestions': lookup['brand_suggestions'],
        'brand_suggestions_en': lookup['brand_suggestions_en'],
        'popular_brands': lookup['popular_brands'],
        'engine_type_choices': CarSpecification.ENGINE_TYPE_CHOICES,
        'spec_region_choices': [{'value': v, 'label': l} for v, l in CarSpecification.SPEC_REGION_CHOICES],
        'trim_choices': lookup['trim_choices'],
        'brand': brand,
        'model': model,
        'year': year,
        'engine': engine,
        'engine_type': engine_type,
        'spec_region': spec_region,
        'fuel': fuel,
        'trim': trim,
    }


def index_view(request):
    banners = AdBanner.objects.filter(is_active=True).order_by('order', '-created_at')
    feature_cards = FeatureCard.objects.filter(is_active=True).order_by('order', 'created_at')
    context = {
        'banners': banners,
        'feature_cards': feature_cards,
    }
    return render(request, 'cars/index.html', context)


def search_view(request):
    context = _search_context(request)
    context['banners'] = AdBanner.objects.filter(is_active=True).order_by('order', '-created_at')
    return render(request, 'cars/search.html', context)


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

        trims = list(
            narrow(base_qs())
            .exclude(trim__isnull=True)
            .exclude(trim='')
            .values_list('trim', flat=True)
            .distinct()
            .order_by('trim')[:200]
        )
        return JsonResponse({'models': models, 'engines': engines, 'trims': trims})

    return JsonResponse({'models': [], 'engines': []})


def is_staff_user(user):
    return user.is_authenticated and user.is_staff


@login_required
@user_passes_test(is_staff_user)
def import_excel_view(request):
    form = CsvImportForm()

    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        try:
            result = import_cars_from_excel(excel_file)
            
            if result['success']:
                success_msg = f"\u2705 \u062a\u0645 \u0627\u0644\u0627\u0633\u062a\u064a\u0631\u0627\u062f \u0628\u0646\u062c\u0627\u062d! \u0625\u0636\u0627\u0641\u0629 {result['created']} \u0648\u062a\u062d\u062f\u064a\u062b {result['updated']}."
                if result['failed'] > 0:
                    success_msg += f" \u274c \u0641\u0634\u0644 {result['failed']} \u0635\u0641."
                    for failed_row in result['failed_rows'][:5]:
                        messages.warning(request, f"\u0627\u0644\u0635\u0641 {failed_row['row_number']}: {failed_row['error']}")
                messages.success(request, success_msg)
            else:
                for error in result['errors']:
                    messages.error(request, f"\u274c {error}")
                    
        except Exception:
            import logging
            logging.getLogger('cars').exception('Excel import failed')
            messages.error(request, "\u26a0\ufe0f \u062d\u062f\u062b \u062e\u0637\u0623 \u0623\u062b\u0646\u0627\u0621 \u0645\u0639\u0627\u0644\u062c\u0629 \u0627\u0644\u0645\u0644\u0641. \u062a\u0623\u0643\u062f \u0645\u0646 \u0627\u0644\u0635\u064a\u063a\u0629 \u0648\u0623\u0639\u062f \u0627\u0644\u0645\u062d\u0627\u0648\u0644\u0629.")
        
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
                messages.error(request, "\u26a0\ufe0f \u0633\u0639\u0629 \u0627\u0644\u062e\u0632\u0627\u0646 \u064a\u062c\u0628 \u0623\u0646 \u062a\u0643\u0648\u0646 \u0623\u0643\u0628\u0631 \u0645\u0646 \u0635\u0641\u0631")
                return render(request, 'cars/mix_calculator.html', {'cars': CarSpecification.objects.all().order_by('brand_ar', 'model_ar'), 'result': result})
            
            if o1 < 80 or o1 > 120 or o2 < 80 or o2 > 120:
                messages.error(request, "\u26a0\ufe0f \u0631\u0642\u0645 \u0627\u0644\u0623\u0648\u0643\u062a\u0627\u0646 \u064a\u062c\u0628 \u0623\u0646 \u064a\u0643\u0648\u0646 \u0628\u064a\u0646 80 \u0648 120")
                return render(request, 'cars/mix_calculator.html', {'cars': CarSpecification.objects.all().order_by('brand_ar', 'model_ar'), 'result': result})
            
            if not (min(o1, o2) <= target <= max(o1, o2)):
                messages.error(request, "\u26a0\ufe0f \u0627\u0644\u0623\u0648\u0643\u062a\u0627\u0646 \u0627\u0644\u0645\u0637\u0644\u0648\u0628 \u064a\u062c\u0628 \u0623\u0646 \u064a\u0643\u0648\u0646 \u0628\u064a\u0646 \u0627\u0644\u0646\u0648\u0639\u064a\u0646")
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
                messages.success(request, "\u2705 \u062a\u0645 \u062d\u0633\u0627\u0628 \u0627\u0644\u062e\u0644\u0637\u0629 \u0628\u0646\u062c\u0627\u062d!")
        except ValueError:
            messages.error(request, "\u26a0\ufe0f \u064a\u0631\u062c\u0649 \u0625\u062f\u062e\u0627\u0644 \u0623\u0631\u0642\u0627\u0645 \u0635\u062d\u064a\u062d\u0629.")
        except ZeroDivisionError:
            messages.error(request, "\u26a0\ufe0f \u062d\u062f\u062b \u062e\u0637\u0623 \u0641\u064a \u0627\u0644\u062d\u0633\u0627\u0628. \u062a\u0623\u0643\u062f \u0645\u0646 \u0627\u0644\u0642\u064a\u0645 \u0627\u0644\u0645\u062f\u062e\u0644\u0629.")
    
    cars = CarSpecification.objects.all().only('id', 'brand_ar', 'model_ar', 'year', 'octane', 'oil_capacity').order_by('brand_ar', 'model_ar')
    return render(request, 'cars/mix_calculator.html', {'cars': cars, 'result': result})


def recommendations_view(request, car_id):
    try:
        car = CarSpecification.objects.get(id=car_id)
    except CarSpecification.DoesNotExist:
        messages.error(request, "\u26a0\ufe0f \u0627\u0644\u0633\u064a\u0627\u0631\u0629 \u063a\u064a\u0631 \u0645\u0648\u062c\u0648\u062f\u0629")
        return redirect('index')
    return render(request, 'cars/recommendations.html', {'car': car})


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

    host = request.build_absolute_uri('/').rstrip('/')
    today = timezone.localdate().isoformat()

    urls = [
        {'loc': host, 'priority': '1.0', 'freq': 'daily'},
        {'loc': host + reverse('search'), 'priority': '0.9', 'freq': 'daily'},
        {'loc': host + reverse('mix_calculator'), 'priority': '0.8', 'freq': 'weekly'},
        {'loc': host + reverse('budget_finder'), 'priority': '0.7', 'freq': 'weekly'},
        {'loc': host + reverse('about'), 'priority': '0.5', 'freq': 'monthly'},
        {'loc': host + reverse('privacy'), 'priority': '0.3', 'freq': 'yearly'},
    ]
    for car_id in CarSpecification.objects.values_list('id', flat=True).iterator():
        urls.append({
            'loc': host + reverse('recommendations', args=[car_id]),
            'priority': '0.7',
            'freq': 'monthly',
        })

    chunk = '\n'.join(
        f"   <url><loc>{u['loc']}</loc><lastmod>{today}</lastmod>"
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


def budget_finder_view(request):
    from .services.deepseek_service import find_cars_by_budget

    if request.method == 'POST':
        budget_raw = request.POST.get('budget', '').strip().replace(',', '').replace(' ', '')
        currency = request.POST.get('currency', 'iqd')
        car_type = request.POST.get('car_type', 'all')
        condition = request.POST.get('condition', 'used')

        try:
            budget = int(float(budget_raw))
        except (ValueError, TypeError):
            messages.error(request, "\u26a0\ufe0f \u0623\u062f\u062e\u0644 \u0645\u0628\u0644\u063a \u0635\u062d\u064a\u062d")
            return render(request, 'cars/budget_finder.html', {'show_form': True})

        if budget <= 0:
            messages.error(request, "\u26a0\ufe0f \u0627\u0644\u0645\u0628\u0644\u063a \u064a\u062c\u0628 \u0623\u0646 \u064a\u0643\u0648\u0646 \u0623\u0643\u0628\u0631 \u0645\u0646 \u0635\u0641\u0631")
            return render(request, 'cars/budget_finder.html', {'show_form': True})

        result = find_cars_by_budget(budget, currency, car_type, condition)

        return render(request, 'cars/budget_finder.html', {
            'result': result,
            'budget': budget,
            'currency': currency,
            'car_type': car_type,
            'condition': condition,
            'show_form': False,
        })

    return render(request, 'cars/budget_finder.html', {'show_form': True})


def search_ai_suggest(request):
    from .services.deepseek_service import suggest_cars_ai
    brand = request.GET.get('brand', '').strip()
    model = request.GET.get('model', '').strip()
    year = request.GET.get('year', '').strip()
    engine = request.GET.get('engine', '').strip()
    if not (brand or model or year or engine):
        return render(request, 'cars/_ai_suggestions.html', {'ai_result': {'success': False}})
    result = suggest_cars_ai(brand=brand, model=model, year=year, engine=engine)
    return render(request, 'cars/_ai_suggestions.html', {'ai_result': result})
