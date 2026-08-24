import pandas as pd
import re
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.http import JsonResponse
from django import forms
from .models import CarSpecification, AdBanner, FeatureCard
from .services.excel_importer import import_cars_from_excel


class CsvImportForm(forms.Form):
    excel_file = forms.FileField(label="اختر ملف الأكسل")


def normalize_engine(value):
    """تطبيع قيمة المحرك لتوحيد 2000 = 2.0 = 2L"""
    if not value:
        return value
    
    value = str(value).strip()
    
    numbers = re.findall(r'(\d+\.?\d*)', value)
    if numbers:
        num = float(numbers[0])
        if num >= 1000:
            num = num / 1000
        if num == int(num):
            return f"{int(num)}.0"
        return f"{num}"
    
    return value


def index_view(request):
    brand = request.GET.get('brand', '').strip()
    model = request.GET.get('model', '').strip()
    year = request.GET.get('year', '').strip()
    engine = request.GET.get('engine', '').strip()
    engine_type = request.GET.get('engine_type', '').strip()
    spec_region = request.GET.get('spec_region', '').strip()

    filters = Q()
    
    # شروط البحث الأساسية
    if brand:
        filters &= Q(brand_ar__icontains=brand) | Q(brand_en__icontains=brand)
    if model:
        filters &= Q(model_ar__icontains=model) | Q(model_en__icontains=model)
    if year:
        try:
            filters &= Q(year=int(year))
        except ValueError:
            filters &= Q(year__icontains=year)
    if engine_type:
        filters &= Q(engine_type__icontains=engine_type)
    if spec_region:
        filters &= Q(spec_region__icontains=spec_region)
    
    # ✅ بناء شرط المحرك بشكل مستقل (تم إصلاحه)
    engine_q = Q()
    if engine:
        normalized_engine = normalize_engine(engine)
        
        # البدائل الأساسية
        engine_q |= Q(engine__icontains=engine)
        engine_q |= Q(engine__icontains=normalized_engine)
        engine_q |= Q(engine__icontains=engine.replace('.', ''))
        engine_q |= Q(engine__icontains=engine.replace(',', ''))
        
        # بدائل الأرقام
        numbers = re.findall(r'(\d+\.?\d*)', engine)
        if numbers:
            num = float(numbers[0])
            if num >= 1000:
                engine_q |= Q(engine__icontains=str(int(num)))
                engine_q |= Q(engine__icontains=f"{num/1000:.1f}")
                engine_q |= Q(engine__icontains=f"{int(num/1000)}.0")
                engine_q |= Q(engine__icontains=f"{int(num/1000)}L")
            else:
                engine_q |= Q(engine__icontains=str(int(num*1000)))
                engine_q |= Q(engine__icontains=f"{num:.1f}")
                engine_q |= Q(engine__icontains=f"{int(num)}.0")
                engine_q |= Q(engine__icontains=f"{int(num)}L")
        
        # ربط شرط المحرك مع باقي الشروط
        filters &= engine_q

    if filters:
        cars = CarSpecification.objects.filter(filters)
    else:
        cars = None

    # جلب البنرات مع caching بسيط
    banners = AdBanner.objects.filter(is_active=True).order_by('order', '-created_at')

    # ✅ بطاقات المميزات (تُدار من لوحة الأدمن)
    feature_cards = FeatureCard.objects.filter(is_active=True).order_by('order', 'created_at')

    # تحسين اقتراحات الماركات
    brand_suggestions = list(CarSpecification.objects.values_list('brand_ar', flat=True).distinct().order_by('brand_ar')[:100])
    
    engine_type_choices = CarSpecification.ENGINE_TYPE_CHOICES
    spec_region_choices = CarSpecification.SPEC_REGION_CHOICES
    spec_region_display = [{'value': v, 'label': l} for v, l in spec_region_choices]

    context = {
        'cars': cars,
        'banners': banners,
        'feature_cards': feature_cards,
        'brand_suggestions': brand_suggestions,
        'engine_type_choices': engine_type_choices,
        'spec_region_choices': spec_region_display,
        'brand': brand,
        'model': model,
        'year': year,
        'engine': engine,
        'engine_type': engine_type,
        'spec_region': spec_region,
    }
    return render(request, 'cars/index.html', context)


def get_suggestions(request):
    brand = request.GET.get('brand', '').strip()
    model = request.GET.get('model', '').strip()

    if brand and not model:
        models_list = list(CarSpecification.objects.filter(
            Q(brand_ar__icontains=brand) | Q(brand_en__icontains=brand)
        ).values_list('model_ar', flat=True).distinct().order_by('model_ar')[:50])
        return JsonResponse({'models': models_list, 'engines': []})

    if brand and model:
        engines = list(CarSpecification.objects.filter(
            Q(brand_ar__icontains=brand) | Q(brand_en__icontains=brand),
            Q(model_ar__icontains=model) | Q(model_en__icontains=model)
        ).values_list('engine', flat=True).distinct().order_by('engine')[:50])
        return JsonResponse({'models': [], 'engines': engines})

    return JsonResponse({'models': [], 'engines': []})


def is_staff_user(user):
    """التحقق من أن المستخدم لديه صلاحيات staff"""
    return user.is_authenticated and user.is_staff


@login_required
@user_passes_test(is_staff_user)
def import_excel_view(request):
    """
    صفحة استيراد Excel - محمية بصلاحيات المشرفين فقط
    """
    form = CsvImportForm()

    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        try:
            # استخدام خدمة الاستيراد الموحدة
            result = import_cars_from_excel(excel_file)
            
            if result['success']:
                # عرض تقرير مفصل
                success_msg = f"✅ تم الاستيراد بنجاح! إضافة {result['created']} وتحديث {result['updated']}."
                if result['failed'] > 0:
                    success_msg += f" ❌ فشل {result['failed']} صف."
                    # عرض تفاصيل الصفوف الفاشلة
                    for failed_row in result['failed_rows'][:5]:  # عرض أول 5 أخطاء فقط
                        messages.warning(request, f"الصف {failed_row['row_number']}: {failed_row['error']}")
                messages.success(request, success_msg)
            else:
                for error in result['errors']:
                    messages.error(request, f"❌ {error}")
                    
        except Exception as e:
            messages.error(request, f"خطأ غير متوقع: {str(e)}")
        
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
            
            # التحقق من صحة القيم
            if tank <= 0:
                messages.error(request, "⚠️ سعة الخزان يجب أن تكون أكبر من صفر")
                return render(request, 'cars/mix_calculator.html', {'cars': CarSpecification.objects.all().order_by('brand_ar', 'model_ar'), 'result': result})
            
            if o1 < 80 or o1 > 120 or o2 < 80 or o2 > 120:
                messages.error(request, "⚠️ رقم الأوكتان يجب أن يكون بين 80 و 120")
                return render(request, 'cars/mix_calculator.html', {'cars': CarSpecification.objects.all().order_by('brand_ar', 'model_ar'), 'result': result})
            
            if not (min(o1, o2) <= target <= max(o1, o2)):
                messages.error(request, "⚠️ الأوكتان المطلوب يجب أن يكون بين النوعين")
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
                messages.success(request, "✅ تم حساب الخلطة بنجاح!")
        except ValueError:
            messages.error(request, "⚠️ يرجى إدخال أرقام صحيحة.")
        except ZeroDivisionError:
            messages.error(request, "⚠️ حدث خطأ في الحساب. تأكد من القيم المدخلة.")
    
    # تحسين: استخدام only() لجلب الحقول المطلوبة فقط
    cars = CarSpecification.objects.all().only('id', 'brand_ar', 'model_ar', 'year', 'octane', 'oil_capacity').order_by('brand_ar', 'model_ar')
    return render(request, 'cars/mix_calculator.html', {'cars': cars, 'result': result})


def recommendations_view(request, car_id):
    try:
        car = CarSpecification.objects.get(id=car_id)
    except CarSpecification.DoesNotExist:
        messages.error(request, "⚠️ السيارة غير موجودة")
        return redirect('index')
    return render(request, 'cars/recommendations.html', {'car': car})