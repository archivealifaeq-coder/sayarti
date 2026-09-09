import pandas as pd
from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import redirect
from django import forms
from django.http import HttpResponse
from django.template import Template, RequestContext
from django.utils.html import format_html, mark_safe
from django.core.cache import cache
from django.db.models import Count
from django.db import models as db_models
from .models import CarSpecification, AdBanner, FeatureCard, SiteSettings, Sponsor, PromoCode, MarketCarPrice, MarketCarPriceCandidate
from .services.excel_importer import import_cars_from_excel
from .services.online_market_scraper import run_online_update


class CsvImportForm(forms.Form):
    excel_file = forms.FileField(label="اختر ملف الأكسل")


class OnlineMarketUpdateForm(forms.Form):
    SOURCE_CHOICES = [
        ('opensooq', 'السوق المفتوح العراق'),
    ]
    BRAND_CHOICES = [
        ('toyota', 'تويوتا'),
        ('hyundai', 'هيونداي'),
        ('kia', 'كيا'),
        ('nissan', 'نيسان'),
        ('chevrolet', 'شيفروليه'),
        ('mg', 'MG'),
        ('chery', 'شيري'),
        ('geely', 'جيلي'),
        ('saipa', 'سايبا'),
        ('samand', 'سمند'),
    ]

    source = forms.ChoiceField(label='مصدر الأسعار', choices=SOURCE_CHOICES)
    brands = forms.MultipleChoiceField(
        label='الماركات المستهدفة',
        choices=BRAND_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        initial=['toyota', 'hyundai', 'kia', 'nissan', 'chevrolet'],
    )
    max_pages = forms.IntegerField(label='عدد الصفحات لكل ماركة', min_value=1, max_value=10, initial=2)
    OPTIONAL_FIELD_CHOICES = [
        ('trim', 'محاولة تحديد الفئة / الكلاس'),
        ('engine', 'محاولة استخراج نوع/حجم المحرك'),
        ('price_usd', 'حساب السعر بالدولار'),
        ('body_type', 'محاولة تحديد نوع الجسم'),
        ('pros', 'حفظ عنوان الإعلان كملاحظة/سبب ترشيح'),
    ]
    optional_fields = forms.MultipleChoiceField(
        label='الحقول الاختيارية التي تريد تعبئتها تلقائياً',
        choices=OPTIONAL_FIELD_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        initial=['trim', 'engine', 'price_usd', 'body_type', 'pros'],
    )
    review_only = forms.BooleanField(
        label='حفظ النتائج للمراجعة فقط وعدم عرضها للزائر مباشرة',
        required=False,
        initial=True,
        disabled=True,
    )


@admin.register(CarSpecification)
class CarSpecificationAdmin(admin.ModelAdmin):
    change_list_template = 'admin/cars_changelist.html'

    list_display = (
        'id', 
        'brand_ar_display', 
        'model_ar_display', 
        'year_display', 
        'trim_display', 
        'engine_type_badge', 
        'spec_region_badge', 
        'service_summary',
    )
    
    list_display_links = ('id', 'brand_ar_display', 'model_ar_display')
    
    list_filter = (
        'brand_ar', 
        'year', 
        'engine_type', 
        'spec_region', 
        'octane'
    )
    
    search_fields = (
        'brand_ar', 
        'brand_en', 
        'model_ar', 
        'model_en', 
        'trim',
        'id', 
        'tire_size',
        'transmission_type',
        'battery'
    )
    
    ordering = ('brand_ar', 'model_ar', '-year')
    
    list_per_page = 30
    
    actions = ['make_gcc_spec', 'make_american_spec', 'make_european_spec', 'delete_selected']
    
    fieldsets = (
        ('📋 المعلومات الأساسية', {
            'fields': ('id', 'brand_ar', 'brand_en', 'model_ar', 'model_en', 'year', 'trim', 'spec')
        }),
        ('⚙️ المحرك والمواصفات', {
            'fields': ('engine', 'engine_type', 'spec_region')
        }),
        ('🛢️ الزيت', {
            'fields': ('oil_visc', 'oil_visc_high_km', 'oil_capacity', 'oil_brands')
        }),
        ('⚡ البطارية وناقل الحركة', {
            'fields': ('battery', 'transmission_type', 'transmission_oil_spec', 'transmission_oil_brands')
        }),
        ('⛽ الوقود', {
            'fields': ('fuel', 'octane')
        }),
        ('🛞 الإطارات والشمعات', {
            'fields': ('tire_size', 'spark')
        }),
        ('📝 توصيات إضافية', {
            'fields': ('recommendations',),
            'classes': ('collapse',)
        }),
    )
    
    def brand_ar_display(self, obj):
        return format_html('<span style="font-weight: bold; color: #b45309;">{}</span>', obj.brand_ar)
    brand_ar_display.short_description = 'الماركة'
    
    def model_ar_display(self, obj):
        return format_html('<span style="color: #1e293b; font-weight:600;">{}</span>', obj.model_ar)
    model_ar_display.short_description = 'الموديل'
    
    def year_display(self, obj):
        return format_html('<span style="background:#dbeafe; padding:2px 10px; border-radius:12px; color:#1d4ed8; font-weight:700;">{}</span>', obj.year)
    year_display.short_description = 'السنة'

    def trim_display(self, obj):
        if obj.trim:
            return format_html('<span style="color: #db2777; font-weight: bold;">{}</span>', obj.trim)
        return mark_safe('<span style="color: #64748b;">—</span>')
    trim_display.short_description = 'الفئة (Trim)'
    
    def octane_display(self, obj):
        return format_html('<span style="background:#fef3c7; padding:2px 12px; border-radius:12px; color:#b45309; font-weight:bold;">{}</span>', obj.octane)
    octane_display.short_description = 'الأوكتان'
    
    def tire_size_display(self, obj):
        return format_html('<span style="color: #1d4ed8; font-weight:600;">{}</span>', obj.tire_size or 'غير محدد')
    tire_size_display.short_description = 'حجم الإطار'

    def service_summary(self, obj):
        return format_html(
            '<div class="admin-service-summary">'
            '<span title="الأوكتان">⛽ {}</span>'
            '<span title="زيت المحرك">🛢️ {}</span>'
            '<span title="الإطار">🛞 {}</span>'
            '<span title="البطارية">🔋 {}</span>'
            '</div>',
            obj.octane or '—',
            obj.oil_visc or '—',
            obj.tire_size or '—',
            obj.battery or '—',
        )
    service_summary.short_description = 'مختصر الخدمة'
    
    def engine_type_badge(self, obj):
        colors = {
            'regular': '#475569',
            'hybrid': '#15803d',
            'turbo': '#dc2626',
            'diesel': '#b45309',
            'electric': '#1d4ed8',
        }
        color = colors.get(obj.engine_type, '#475569')
        return format_html('<span style="background: {}20; padding: 2px 12px; border-radius: 12px; color: {}; font-size: 0.8rem;">{}</span>', 
                          color, color, obj.get_engine_type_display())
    engine_type_badge.short_description = 'نوع المحرك'
    
    def spec_region_badge(self, obj):
        colors = {
            'gcc': '#15803d',
            'american': '#1d4ed8',
            'european': '#b45309',
            'japanese': '#be185d',
            'chinese': '#dc2626',
            'other': '#475569',
        }
        color = colors.get(obj.spec_region, '#475569')
        return format_html('<span style="background: {}20; padding: 2px 12px; border-radius: 12px; color: {}; font-size: 0.8rem;">{}</span>', 
                          color, color, obj.get_spec_region_display())
    spec_region_badge.short_description = 'المواصفات'
    
    def make_gcc_spec(self, request, queryset):
        updated = queryset.update(spec_region='gcc')
        self.message_user(request, f'✅ تم تحديث {updated} سيارة إلى مواصفات خليجية', messages.SUCCESS)
    make_gcc_spec.short_description = '🌍 تغيير المواصفات إلى خليجي'
    
    def make_american_spec(self, request, queryset):
        updated = queryset.update(spec_region='american')
        self.message_user(request, f'✅ تم تحديث {updated} سيارة إلى مواصفات أمريكية', messages.SUCCESS)
    make_american_spec.short_description = '🌍 تغيير المواصفات إلى أمريكي'
    
    def make_european_spec(self, request, queryset):
        updated = queryset.update(spec_region='european')
        self.message_user(request, f'✅ تم تحديث {updated} سيارة إلى مواصفات أوروبية', messages.SUCCESS)
    make_european_spec.short_description = '🌍 تغيير المواصفات إلى أوروبي'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-excel/', self.admin_site.admin_view(self.import_excel_view), name='car_import_excel'),
        ]
        return custom_urls + urls

    def import_excel_view(self, request):
        if request.method == "POST":
            excel_file = request.FILES.get("excel_file")
            if excel_file:
                try:
                    result = import_cars_from_excel(excel_file)
                    from django.core.cache import cache
                    cache.delete('lookup_data')
                    
                    if result['success']:
                        success_msg = f"✅ تم الاستيراد بنجاح! إضافة {result['created']} وتحديث {result['updated']}."
                        if result['failed'] > 0:
                            success_msg += f" ❌ فشل {result['failed']} صف."
                            for failed_row in result['failed_rows'][:5]:
                                self.message_user(request, f"⚠️ الصف {failed_row['row_number']}: {failed_row['error']}", messages.WARNING)
                        self.message_user(request, success_msg, messages.SUCCESS)
                    else:
                        for error in result['errors']:
                            self.message_user(request, f"❌ {error}", messages.ERROR)
                            
                except Exception:
                    import logging
                    logging.getLogger('cars').exception('Admin Excel import failed')
                    self.message_user(request, "❌ حدث خطأ غير متوقع أثناء الاستيراد. راجع السجلات.", messages.ERROR)
            else:
                self.message_user(request, "لم يتم اختيار ملف.", messages.WARNING)
            
            return redirect("..")

        form = CsvImportForm()
        html_template = """
        {% extends "admin/base_site.html" %}
        {% block content %}
        <div class="section-card" style="max-width: 600px; margin: 20px auto;">
            <h3>📊 استيراد بيانات السيارات</h3>
            <form method="POST" enctype="multipart/form-data">
                {% csrf_token %}
                {{ form.as_p }}
                <button type="submit" class="btn btn-primary" style="border:none;">رفع الملف 🚀</button>
                <a href="../" style="color:#64748b; margin-right:10px;">إلغاء</a>
            </form>
        </div>
        {% endblock %}
        """
        t = Template(html_template)
        c = RequestContext(request, {"form": form, "opts": self.model._meta})
        return HttpResponse(t.render(c))

    def save_model(self, request, obj, form, change):
        from django.core.cache import cache
        cache.delete('lookup_data')
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        from django.core.cache import cache
        cache.delete('lookup_data')
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        from django.core.cache import cache
        cache.delete('lookup_data')
        super().delete_queryset(request, queryset)


class AdBannerForm(forms.ModelForm):
    class Meta:
        model = AdBanner
        fields = '__all__'
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'مثال: خصم 20% على زيت المحرك',
                'style': 'width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #ddd;'
            }),
            'subtitle': forms.TextInput(attrs={
                'placeholder': 'مثال: أداء أفضل - توفير في الوقود',
                'style': 'width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #ddd;'
            }),
            'image': forms.FileInput(attrs={
                'style': 'width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #ddd;'
            }),
            'image_mobile': forms.FileInput(attrs={
                'style': 'width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #ddd;'
            }),
            'background_color': forms.Select(attrs={
                'style': 'width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #ddd;'
            }),
            'button_text': forms.TextInput(attrs={
                'placeholder': 'اعرف المزيد',
                'style': 'width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #ddd;'
            }),
            'button_url': forms.URLInput(attrs={
                'placeholder': 'https://example.com',
                'style': 'width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #ddd;'
            }),
            'order': forms.NumberInput(attrs={
                'style': 'width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #ddd;'
            }),
        }


@admin.register(AdBanner)
class AdBannerAdmin(admin.ModelAdmin):
    form = AdBannerForm

    list_display = (
        'title_preview', 
        'position_badge', 
        'sponsor_display',
        'order',
        'is_active',
        'created_at_display'
    )
    
    list_editable = ('order', 'is_active')
    list_filter = ('position', 'is_active', 'sponsor')
    search_fields = ('title', 'subtitle', 'button_text', 'sponsor__name')
    ordering = ('position', 'order', '-created_at')
    list_per_page = 20
    list_select_related = ('sponsor',)

    fieldsets = (
        ('📝 المحتوى', {
            'fields': ('title', 'subtitle', 'position')
        }),
        ('🎟️ ربط كود الخصم (اختياري)', {
            'fields': ('sponsor',),
            'description': 'اختر شركة راعية ليظهر زر «احصل على خصم» في هذا الإعلان. اتركه فارغاً لبنر عادي بدون خصم.',
            'classes': ('collapse',),
        }),
        ('🖼️ الصور', {
            'fields': ('image', 'image_mobile'),
            'description': '📸 سطح المكتب: 1920×820 بكسل (21:9) | 📱 الهاتف: 800×600 بكسل (4:3)',
            'classes': ('collapse',),
        }),
        ('🎨 الألوان (احتياطي)', {
            'fields': ('background_color', 'text_color'),
            'classes': ('collapse',)
        }),
        ('🔗 الرابط', {
            'fields': ('button_text', 'button_url')
        }),
        ('⚙️ الإعدادات', {
            'fields': ('order', 'is_active')
        }),
    )
    
    def title_preview(self, obj):
        icon = '📢' if obj.position == 'ticker' else '🎠'
        color = '#b45309' if obj.is_active else '#475569'
        return format_html('<span style="color: {}; font-weight:600;">{} {}</span>', color, icon, obj.title[:40])
    title_preview.short_description = 'العنوان'
    
    def position_badge(self, obj):
        if obj.position == 'ticker':
            return mark_safe('<span style="background:#dbeafe; padding:2px 12px; border-radius:12px; color:#1d4ed8;">📢 شريط متحرك</span>')
        return mark_safe('<span style="background:#fef3c7; padding:2px 12px; border-radius:12px; color:#b45309;">🎠 سلايدر</span>')
    position_badge.short_description = 'الموقع'
    
    def sponsor_display(self, obj):
        if obj.sponsor_id:
            return format_html('<span style="background:#ede9fe; padding:2px 12px; border-radius:12px; color:#6d28d9;">🎟️ {}</span>', obj.sponsor.name)
        return mark_safe('<span style="color:#475569;">—</span>')
    sponsor_display.short_description = 'الشركة'

    def created_at_display(self, obj):
        return format_html('<span style="color: #64748b; font-size: 0.8rem;">{}</span>', obj.created_at.strftime('%Y-%m-%d %H:%M'))
    created_at_display.short_description = 'تاريخ الإضافة'
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'position':
            kwargs['widget'] = forms.Select(choices=[
                ('ticker', '📢 شريط متحرك علوي (5%) - أعلى الصفحة'),
                ('slider', '🎠 سلايدر رئيسي (35%) - وسط الصفحة'),
            ])
        elif db_field.name == 'background_color':
            kwargs['widget'] = forms.Select(choices=[
                ('from-amber-600 via-orange-600 to-red-700', '🔥 برتقالي-أحمر (للشريط)'),
                ('from-blue-700 via-cyan-600 to-teal-700', '🌊 أزرق-فيروزي (للشريط)'),
                ('from-purple-700 via-pink-600 to-rose-700', '💗 بنفسجي-وردي (للشريط)'),
                ('from-green-600 via-emerald-600 to-teal-700', '🌿 أخضر-زمردي (للشريط)'),
                ('from-yellow-500 via-amber-500 to-orange-500', '⭐ أصفر-برتقالي (للشريط)'),
                ('from-red-600 via-rose-600 to-pink-600', '❤️ أحمر-وردي (للشريط)'),
                ('from-indigo-700 via-purple-700 to-pink-700', '💜 نيلي-بنفسجي (للشريط)'),
                ('from-blue-700 via-indigo-700 to-purple-700', '💜 أزرق-بنفسجي (سلايدر)'),
                ('from-amber-500 via-orange-500 to-red-500', '🔥 برتقالي-أحمر (سلايدر)'),
                ('from-red-600 via-orange-600 to-yellow-600', '❤️ أحمر-أصفر (سلايدر)'),
                ('from-green-600 via-emerald-600 to-teal-600', '🌿 أخضر-فيروزي (سلايدر)'),
                ('from-purple-700 via-pink-600 to-rose-700', '💗 بنفسجي-وردي (سلايدر)'),
                ('from-cyan-500 via-blue-500 to-indigo-500', '🌊 أزرق-سماوي (سلايدر)'),
                ('from-pink-500 via-rose-500 to-red-500', '🌸 وردي-أحمر (سلايدر)'),
                ('from-slate-700 via-gray-700 to-zinc-700', '⬛ رمادي داكن (سلايدر)'),
                ('from-emerald-500 via-teal-500 to-cyan-500', '💚 زمردي-فيروزي (سلايدر)'),
            ])
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj=None, **kwargs)
        form.base_fields['image'].help_text = '🖼️ الأبعاد الموصى بها: 1920 × 820 بكسل (21:9) — الصورة تُقص تلقائياً'
        form.base_fields['image_mobile'].help_text = '📱 الأبعاد الموصى بها: 800 × 600 بكسل (4:3)'
        return form


@admin.register(FeatureCard)
class FeatureCardAdmin(admin.ModelAdmin):
    list_display = (
        'card_preview',
        'type_badge',
        'order',
        'is_active',
        'created_at_display',
    )
    list_editable = ('order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title', 'description')
    ordering = ('order', 'created_at')
    list_per_page = 20
    fieldsets = (
        ('📝 المحتوى', {
            'fields': ('title', 'description', 'icon')
        }),
        ('📢 إعلان (اختياري)', {
            'fields': ('image', 'link', 'sponsor'),
            'description': '📸 ضع صورة لتتحول البطاقة إلى إعلان، وأضف رابطاً لتصبح قابلة للنقر. الأبعاد الموصى بها: 400×400 بكسل. وعند اختيار شركة راعية يظهر فيها زر «احصل على خصم».'
        }),
        ('⚙️ الإعدادات', {
            'fields': ('order', 'is_active')
        }),
    )

    def card_preview(self, obj):
        color = '#b45309' if obj.is_active else '#475569'
        icon = obj.icon or '🖼️'
        return format_html('<span style="color: {};">{} <b>{}</b></span>', color, icon, obj.title[:40])
    card_preview.short_description = 'البطاقة'

    def type_badge(self, obj):
        if obj.image:
            return mark_safe('<span style="background: #fee2e2; padding: 2px 12px; border-radius: 12px; color: #dc2626;">📢 إعلان</span>')
        return mark_safe('<span style="background: #dcfce7; padding: 2px 12px; border-radius: 12px; color: #15803d;">⭐ مميزة</span>')
    type_badge.short_description = 'النوع'

    def created_at_display(self, obj):
        return format_html('<span style="color: #64748b; font-size: 0.8rem;">{}</span>', obj.created_at.strftime('%Y-%m-%d'))
    created_at_display.short_description = 'التاريخ'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['icon'].help_text = '🚗 🔧 🧮 ⭐ 💧 🛢️ ⚡ — اتركه فارغاً عند استخدام صورة'
        return form


@admin.register(MarketCarPrice)
class MarketCarPriceAdmin(admin.ModelAdmin):
    change_list_template = 'admin/market_prices_changelist.html'
    list_display = ('id1', 'name_display', 'origin_badge', 'body_type_badge', 'condition_badge', 'price_iqd_display', 'price_usd_display', 'confidence_badge', 'updated_at')
    list_filter = ('origin', 'body_type', 'condition', 'is_active', 'updated_at')
    search_fields = ('name', 'brand', 'brand_en', 'model', 'model_en')
    list_per_page = 40
    ordering = ('-year', 'price_iqd', '-confidence', 'brand', 'model')
    fieldsets = (
        ('🚗 السيارة', {
            'fields': ('id1', 'name', 'brand', 'brand_en', 'model', 'model_en', 'year', 'trim', 'origin', 'body_type', 'condition')
        }),
        ('💰 السعر', {
            'fields': ('price_iqd', 'price_usd'),
            'description': 'سعر واحد دقيق قدر الإمكان. البحث في شكد فلوسك يطابق السعر ضمن ±2% فقط.'
        }),
        ('🔧 تفاصيل مختصرة', {
            'fields': ('engine', 'fuel_economy', 'maintenance', 'pros')
        }),
        ('🔎 المصدر والمراجعة', {
            'fields': ('source_name', 'source_url', 'is_active')
        }),
        ('📌 الثقة', {
            'fields': ('confidence',)
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-excel/', self.admin_site.admin_view(self.import_excel_view), name='market_prices_import_excel'),
            path('online-update/', self.admin_site.admin_view(self.online_update_view), name='market_prices_online_update'),
        ]
        return custom_urls + urls

    def online_update_view(self, request):
        existing_prices = MarketCarPrice.objects.count()
        active_prices = MarketCarPrice.objects.filter(is_active=True).count()
        pending_candidates = MarketCarPriceCandidate.objects.filter(status='pending').count()
        form = OnlineMarketUpdateForm(request.POST or None)
        preview = None

        if request.method == 'POST' and form.is_valid():
            selected_brands = [dict(form.fields['brands'].choices).get(v, v) for v in form.cleaned_data['brands']]
            summary = run_online_update(
                source=form.cleaned_data['source'],
                brands=form.cleaned_data['brands'],
                max_pages=form.cleaned_data['max_pages'],
                optional_fields=form.cleaned_data['optional_fields'],
            )
            preview = {
                'source': dict(form.fields['source'].choices).get(form.cleaned_data['source']),
                'brands': selected_brands,
                'max_pages': form.cleaned_data['max_pages'],
                'estimated_requests': len(selected_brands) * form.cleaned_data['max_pages'],
                'fetched': summary.fetched,
                'saved': summary.saved,
                'updated': summary.updated,
                'skipped': summary.skipped,
                'failed': summary.failed,
                'optional_fields': [dict(form.fields['optional_fields'].choices).get(v, v) for v in form.cleaned_data['optional_fields']],
            }
            self.message_user(request, f'تم جلب {summary.fetched} سعر مقترح. جديد: {summary.saved}. محدث: {summary.updated}. فشل مصادر: {summary.failed}.', messages.SUCCESS)

        html_template = """
        {% extends "admin/base_site.html" %}
        {% block content %}
        <style>
            .online-wrap{max-width:1050px;margin:22px auto;direction:rtl}
            .online-hero{background:linear-gradient(135deg,#0f172a,#1d4ed8);color:#fff;border-radius:24px;padding:26px;box-shadow:0 20px 50px rgba(15,23,42,.18)}
            .online-hero h1{margin:0 0 10px;font-size:28px;color:#fff}
            .online-hero p{margin:0;line-height:1.9;color:#dbeafe;font-size:15px}
            .grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:16px}
            .card{background:#fff;border:1px solid #e2e8f0;border-radius:18px;padding:18px;box-shadow:0 10px 30px rgba(15,23,42,.06)}
            .card h3{margin:0 0 10px;color:#0f172a;font-size:18px}
            .metric{font-size:30px;font-weight:800;color:#1d4ed8}
            .muted{color:#64748b;line-height:1.8}
            .flow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}
            .step{background:#f8fafc;border:1px solid #e2e8f0;border-radius:16px;padding:14px;text-align:center;color:#334155;font-weight:700}
            .step strong{display:block;color:#0f172a;margin-bottom:6px}
            .form-box{margin-top:16px;background:#fff;border-radius:20px;border:1px solid #dbeafe;padding:20px}
            .form-box label{font-weight:700;color:#1e293b}
            .form-box select,.form-box input[type=number]{width:100%;max-width:320px;border:1px solid #cbd5e1;border-radius:10px;padding:8px}
            .form-box ul{list-style:none;margin:8px 0 16px;padding:0;columns:2}
            .form-box li{break-inside:avoid;margin:7px 0;color:#334155}
            .safe{background:#ecfdf5;border-color:#bbf7d0;color:#166534}
            .warn{background:#fffbeb;border-color:#fde68a;color:#92400e}
            .actions{display:flex;gap:10px;align-items:center;margin-top:15px;flex-wrap:wrap}
            .btn-main{background:#1d4ed8;color:#fff!important;border-radius:12px;padding:10px 18px;text-decoration:none;border:0;font-weight:800;cursor:pointer}
            .btn-muted{color:#475569!important;text-decoration:none}
            @media(max-width:900px){.grid,.flow{grid-template-columns:1fr}.form-box ul{columns:1}}
        </style>
        <div class="online-wrap">
            <div class="online-hero">
                <h1>التحديث الأونلاين لأسعار شكد فلوسك</h1>
                <p>هذا القسم مخصص للسكربت القادم. الهدف أن يجلب أسعاراً من مواقع الإعلانات، يحللها، ثم يضعها في جدول مراجعة قبل اعتمادها. لا يتم عرض أي سعر للزائر إلا بعد موافقتك.</p>
            </div>

            <div class="grid">
                <div class="card"><h3>إجمالي الأسعار الحالية</h3><div class="metric">{{ existing_prices }}</div><p class="muted">كل سجلات MarketCarPrice.</p></div>
                <div class="card"><h3>الأسعار المفعلة</h3><div class="metric">{{ active_prices }}</div><p class="muted">هذه فقط تظهر في شكد فلوسك.</p></div>
                <div class="card"><h3>بانتظار المراجعة</h3><div class="metric">{{ pending_candidates }}</div><p class="muted">أسعار جلبها السكربت ولم تعتمد بعد.</p></div>
            </div>

            <div class="card" style="margin-top:16px;">
                <h3>المسار الآمن المقترح</h3>
                <div class="flow">
                    <div class="step"><strong>1</strong>جلب من الإنترنت</div>
                    <div class="step"><strong>2</strong>تنظيف واستبعاد الشاذ</div>
                    <div class="step"><strong>3</strong>جدول مراجعة</div>
                    <div class="step"><strong>4</strong>اعتماد يدوي ثم ظهور للزائر</div>
                </div>
                <p class="muted">هذا يمنع ظهور الأسعار الوهمية أو المكررة أمام الزائر، ويجعل السكربت مساعداً لك وليس بديلاً عن مراجعتك.</p>
                <p><a class="btn-main" href="../../marketcarpricecandidate/">فتح جدول مراجعة الأسعار</a></p>
            </div>

            <div class="form-box">
                <h3>خطة تشغيل السكربت</h3>
                <p class="muted">استخدم هذا النموذج لتحديد نطاق التشغيل. النتائج تُحفظ في جدول مراجعة فقط، ولا تظهر للزائر حتى تعتمدها يدوياً.</p>
                <form method="post">
                    {% csrf_token %}
                    {{ form.as_p }}
                    <div class="actions">
                        <button type="submit" class="btn-main">تحضير خطة تشغيل تجريبية</button>
                        <a href="../" class="btn-muted">رجوع إلى أسعار السيارات</a>
                    </div>
                </form>
            </div>

            {% if preview %}
            <div class="card safe" style="margin-top:16px;">
                <h3>نتيجة الخطة التجريبية</h3>
                <p>المصدر: <b>{{ preview.source }}</b></p>
                <p>الماركات: <b>{{ preview.brands|join:", " }}</b></p>
                <p>عدد الصفحات لكل ماركة: <b>{{ preview.max_pages }}</b></p>
                <p>عدد طلبات الجلب المتوقع: <b>{{ preview.estimated_requests }}</b></p>
                <p>الحقول الاختيارية المختارة: <b>{{ preview.optional_fields|join:", " }}</b></p>
                <p>تم الجلب: <b>{{ preview.fetched }}</b> | جديد: <b>{{ preview.saved }}</b> | محدث: <b>{{ preview.updated }}</b> | متروك: <b>{{ preview.skipped }}</b> | فشل مصادر: <b>{{ preview.failed }}</b></p>
                <p>الحفظ النهائي سيكون في جدول مراجعة أولاً، وليس في أسعار شكد فلوسك مباشرة.</p>
            </div>
            {% endif %}
        </div>
        {% endblock %}
        """
        t = Template(html_template)
        c = RequestContext(request, {
            'form': form,
            'preview': preview,
            'existing_prices': existing_prices,
            'active_prices': active_prices,
            'pending_candidates': pending_candidates,
            'opts': self.model._meta,
        })
        return HttpResponse(t.render(c))

    def import_excel_view(self, request):
        if request.method == 'POST':
            excel_file = request.FILES.get('excel_file')
            if not excel_file:
                self.message_user(request, 'لم يتم اختيار ملف.', messages.WARNING)
                return redirect('.')
            if excel_file.size > 10 * 1024 * 1024:
                self.message_user(request, 'الملف كبير جداً. الحد الأقصى 10 ميجابايت.', messages.ERROR)
                return redirect('.')
            if not excel_file.name.lower().endswith(('.xlsx', '.xls')):
                self.message_user(request, 'يجب أن يكون الملف بصيغة Excel (.xlsx أو .xls).', messages.ERROR)
                return redirect('.')
            try:
                df = pd.read_excel(excel_file)
                required = {'name', 'brand_ar', 'model_ar', 'year', 'origin', 'body_type', 'condition'}
                missing = required - set(df.columns)
                if missing:
                    self.message_user(request, 'أعمدة ناقصة: ' + ', '.join(sorted(missing)), messages.ERROR)
                    return redirect('.')

                def to_int(value, default=None):
                    if pd.isna(value) or value == '':
                        return default
                    return int(float(str(value).replace(',', '').strip()))

                def origin_value(value):
                    value = str(value or '').strip().lower()
                    return {
                        'عام': 'all', 'الكل': 'all', 'all': 'all',
                        'ياباني': 'japanese', 'japanese': 'japanese',
                        'كوري': 'korean', 'korean': 'korean',
                        'صيني': 'chinese', 'chinese': 'chinese',
                        'أمريكي': 'american', 'امريكي': 'american', 'american': 'american',
                        'ألماني': 'german', 'الماني': 'german', 'german': 'german',
                        'أوروبي': 'european', 'اوربي': 'european', 'european': 'european',
                        'إيراني': 'iranian', 'ايراني': 'iranian', 'iranian': 'iranian',
                    }.get(value, 'all')

                def body_type_value(value):
                    value = str(value or '').strip().lower()
                    return {
                        'عام': 'all', 'الكل': 'all', 'all': 'all',
                        'سيدان': 'sedan', 'sedan': 'sedan',
                        'suv': 'suv', 'اس يو في': 'suv', 'عائلي': 'suv', 'عائلية': 'suv',
                        'بيكب': 'pickup', 'بكب': 'pickup', 'pickup': 'pickup',
                        'هاتشباك': 'hatchback', 'hatchback': 'hatchback',
                        'فان': 'van', 'van': 'van',
                        'كوبيه': 'coupe', 'coupe': 'coupe',
                    }.get(value, 'all')

                def condition_value(value):
                    value = str(value or '').strip().lower()
                    return {'جديد': 'new', 'new': 'new', 'مستعمل': 'used', 'used': 'used'}.get(value, 'used')

                saved = 0
                failed = 0
                seen_id1 = set()
                rate = SiteSettings.load().exchange_rate_iqd_per_usd or 1500
                for _, row in df.iterrows():
                    try:
                        id1 = to_int(row.get('id1')) if 'id1' in df.columns else None
                        if id1:
                            if id1 in seen_id1:
                                failed += 1
                                continue
                            seen_id1.add(id1)
                        brand = str(row.get('brand_ar') or row.get('brand') or '').strip()
                        brand_en = str(row.get('brand_en') or '').strip()
                        model = str(row.get('model_ar') or row.get('model') or '').strip()
                        model_en = str(row.get('model_en') or '').strip()
                        year = to_int(row.get('year'))
                        if not (brand and model and year):
                            failed += 1
                            continue
                        price_iqd = to_int(row.get('price_iqd') or row.get('price'))
                        price_usd = to_int(row.get('price_usd'))
                        if not price_iqd and price_usd:
                            price_iqd = int(price_usd * rate)
                        if not price_usd and price_iqd:
                            price_usd = int(price_iqd / rate)
                        if not price_iqd:
                            failed += 1
                            continue
                        lookup = {'id1': id1} if id1 else {
                            'brand': brand,
                            'model': model,
                            'year': year,
                            'origin': origin_value(row.get('origin') or row.get('car_type')),
                            'body_type': body_type_value(row.get('body_type')),
                            'condition': condition_value(row.get('condition')),
                        }
                        trim = str(row.get('trim') or '').strip()
                        engine = str(row.get('engine') or '').strip()
                        if not id1:
                            if trim:
                                lookup['trim'] = trim
                            if engine:
                                lookup['engine'] = engine
                        defaults = {
                            'name': str(row.get('name') or f'{brand} {model} {year}').strip(),
                            'brand': brand,
                            'brand_en': brand_en,
                            'model': model,
                            'model_en': model_en,
                            'year': year,
                            'trim': trim,
                            'origin': origin_value(row.get('origin') or row.get('car_type')),
                            'body_type': body_type_value(row.get('body_type')),
                            'condition': condition_value(row.get('condition')),
                            'price_iqd': price_iqd,
                            'price_usd': price_usd,
                            'engine': engine,
                            'fuel_economy': str(row.get('fuel_economy') or 'جيد').strip(),
                            'maintenance': str(row.get('maintenance') or 'متوسطة').strip(),
                            'pros': str(row.get('pros') or '').strip()[:240],
                            'source_name': str(row.get('source_name') or '').strip(),
                            'source_url': str(row.get('source_url') or '').strip(),
                            'is_active': str(row.get('is_active', '1')).strip().lower() not in ('0', 'false', 'no', 'لا'),
                            'confidence': max(0, min(100, to_int(row.get('confidence'), 80))),
                        }
                        if id1:
                            defaults.pop('id1', None)
                        MarketCarPrice.objects.update_or_create(**lookup, defaults=defaults)
                        saved += 1
                    except Exception:
                        failed += 1
                self.message_user(request, f'تم استيراد/تحديث {saved} سعر. فشل {failed} صف.', messages.SUCCESS if saved else messages.ERROR)
            except Exception:
                import logging
                logging.getLogger('cars').exception('Market price Excel import failed')
                self.message_user(request, 'حدث خطأ أثناء استيراد ملف الأسعار. راجع السجلات.', messages.ERROR)
            return redirect('..')

        form = CsvImportForm()
        html_template = """
        {% extends "admin/base_site.html" %}
        {% block content %}
        <div class="section-card" style="max-width: 760px; margin: 20px auto;">
            <h3>📥 استيراد أسعار السوق من Excel</h3>
            <p style="color:#475569; line-height:1.9;">الأعمدة المطلوبة: name, brand_ar, model_ar, year, origin, body_type, condition. السعر المطلوب: price_iqd أو price_usd. العمود الاختياري id1 رقم خارجي فريد لا يتكرر؛ إذا موجود يتم التحديث عليه بدل إنشاء تكرار. الأعمدة الاختيارية الأخرى: brand_en, model_en, trim, engine, fuel_economy, maintenance, pros, source_name, source_url, is_active, confidence.</p>
            <form method="POST" enctype="multipart/form-data">
                {% csrf_token %}
                {{ form.as_p }}
                <button type="submit" class="btn btn-primary" style="border:none;">استيراد الأسعار</button>
                <a href="../" style="color:#64748b; margin-right:10px;">إلغاء</a>
            </form>
        </div>
        {% endblock %}
        """
        t = Template(html_template)
        c = RequestContext(request, {'form': form, 'opts': self.model._meta})
        return HttpResponse(t.render(c))

    def name_display(self, obj):
        return format_html('<b>{}</b><br><span style="color:#64748b;font-size:.78rem;">{} {} · {}</span>', obj.name, obj.brand, obj.model, obj.year)
    name_display.short_description = 'السيارة'

    def origin_badge(self, obj):
        return format_html('<span class="badge badge-blue">{}</span>', obj.get_origin_display())
    origin_badge.short_description = 'المنشأ'

    def body_type_badge(self, obj):
        return format_html('<span class="badge badge-amber">{}</span>', obj.get_body_type_display())
    body_type_badge.short_description = 'نوع السيارة'

    def condition_badge(self, obj):
        cls = 'badge-green' if obj.condition == 'new' else 'badge-amber'
        return format_html('<span class="badge {}">{}</span>', cls, obj.get_condition_display())
    condition_badge.short_description = 'الحالة'

    def price_iqd_display(self, obj):
        return format_html('<b>{}</b>', f'{obj.price_iqd:,}')
    price_iqd_display.short_description = 'السعر د.ع'

    def price_usd_display(self, obj):
        if not obj.price_usd:
            return '—'
        return format_html('<span class="code-cell">{}</span>', f'{obj.price_usd:,}')
    price_usd_display.short_description = 'السعر $'

    def confidence_badge(self, obj):
        cls = 'badge-green' if obj.confidence >= 80 else 'badge-amber'
        return format_html('<span class="badge {}">{}%</span>', cls, obj.confidence)
    confidence_badge.short_description = 'الثقة'


@admin.register(MarketCarPriceCandidate)
class MarketCarPriceCandidateAdmin(admin.ModelAdmin):
    list_display = ('name_display', 'status_badge', 'origin_badge', 'body_type_badge', 'condition_badge', 'price_iqd_display', 'confidence_badge', 'source_link', 'updated_at')
    list_filter = ('status', 'origin', 'body_type', 'condition', 'source_name', 'updated_at')
    search_fields = ('name', 'brand', 'brand_en', 'model', 'model_en', 'raw_title', 'source_url')
    list_per_page = 40
    ordering = ('status', '-updated_at', '-year', 'price_iqd')
    actions = ['approve_candidates', 'reject_candidates']
    fieldsets = (
        ('بيانات الإعلان', {
            'fields': ('id1', 'raw_title', 'name', 'brand', 'brand_en', 'model', 'model_en', 'year', 'trim')
        }),
        ('التصنيف والسعر', {
            'fields': ('origin', 'body_type', 'condition', 'price_iqd', 'price_usd', 'confidence')
        }),
        ('تفاصيل اختيارية', {
            'fields': ('engine', 'fuel_economy', 'maintenance', 'pros'),
            'description': 'هذه الحقول اختيارية ويمكن تركها فارغة إذا لم يوفرها المصدر الأونلاين.'
        }),
        ('المصدر والمراجعة', {
            'fields': ('source_name', 'source_url', 'status', 'notes')
        }),
    )

    @admin.action(description='اعتماد الأسعار المحددة ونقلها إلى شكد فلوسك')
    def approve_candidates(self, request, queryset):
        approved = 0
        skipped = 0
        for candidate in queryset:
            if candidate.status == 'approved':
                skipped += 1
                continue
            lookup = {'id1': candidate.id1} if candidate.id1 else {
                'brand': candidate.brand,
                'model': candidate.model,
                'year': candidate.year,
                'trim': candidate.trim,
                'origin': candidate.origin,
                'body_type': candidate.body_type,
                'condition': candidate.condition,
            }
            if not candidate.id1 and candidate.engine:
                lookup['engine'] = candidate.engine
            defaults = {
                'name': candidate.name,
                'brand': candidate.brand,
                'brand_en': candidate.brand_en,
                'model': candidate.model,
                'model_en': candidate.model_en,
                'year': candidate.year,
                'trim': candidate.trim,
                'origin': candidate.origin,
                'body_type': candidate.body_type,
                'condition': candidate.condition,
                'price_iqd': candidate.price_iqd,
                'price_usd': candidate.price_usd,
                'engine': candidate.engine,
                'fuel_economy': candidate.fuel_economy or 'جيد',
                'maintenance': candidate.maintenance or 'متوسطة',
                'pros': candidate.pros,
                'source_name': candidate.source_name or 'تحديث أونلاين بعد مراجعة',
                'source_url': candidate.source_url,
                'is_active': True,
                'confidence': max(candidate.confidence, 70),
            }
            if candidate.id1:
                defaults.pop('id1', None)
            MarketCarPrice.objects.update_or_create(**lookup, defaults=defaults)
            candidate.status = 'approved'
            candidate.notes = (candidate.notes + ' | ' if candidate.notes else '') + 'تم الاعتماد ونقله إلى شكد فلوسك.'
            candidate.save(update_fields=['status', 'notes', 'updated_at'])
            approved += 1
        self.message_user(request, f'تم اعتماد {approved} سعر. تم تخطي {skipped}.', messages.SUCCESS)

    @admin.action(description='رفض الأسعار المحددة')
    def reject_candidates(self, request, queryset):
        updated = queryset.exclude(status='approved').update(status='rejected')
        self.message_user(request, f'تم رفض {updated} سعر مقترح.', messages.WARNING)

    def name_display(self, obj):
        return format_html('<b>{}</b><br><span style="color:#64748b;font-size:.78rem;">{} {} · {}</span>', obj.name, obj.brand, obj.model, obj.year)
    name_display.short_description = 'السيارة'

    def status_badge(self, obj):
        colors = {
            'pending': ('#fef3c7', '#92400e'),
            'approved': ('#dcfce7', '#166534'),
            'rejected': ('#fee2e2', '#991b1b'),
        }
        bg, color = colors.get(obj.status, ('#e2e8f0', '#334155'))
        return format_html('<span style="background:{};color:{};padding:3px 10px;border-radius:999px;font-weight:700;">{}</span>', bg, color, obj.get_status_display())
    status_badge.short_description = 'الحالة'

    def origin_badge(self, obj):
        return format_html('<span class="badge badge-blue">{}</span>', obj.get_origin_display())
    origin_badge.short_description = 'المنشأ'

    def body_type_badge(self, obj):
        return format_html('<span class="badge badge-amber">{}</span>', obj.get_body_type_display())
    body_type_badge.short_description = 'نوع السيارة'

    def condition_badge(self, obj):
        return format_html('<span class="badge badge-green">{}</span>', obj.get_condition_display())
    condition_badge.short_description = 'الحالة'

    def price_iqd_display(self, obj):
        return format_html('<b>{}</b>', f'{obj.price_iqd:,}')
    price_iqd_display.short_description = 'السعر د.ع'

    def confidence_badge(self, obj):
        return format_html('<span class="badge badge-blue">{}%</span>', obj.confidence)
    confidence_badge.short_description = 'الثقة'

    def source_link(self, obj):
        if not obj.source_url:
            return obj.source_name or '—'
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', obj.source_url, obj.source_name or 'فتح المصدر')
    source_link.short_description = 'المصدر'

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('settings_summary',)
    fieldsets = (
        ('📢 إعلانات Google AdSense', {
            'fields': ('show_ads', 'adsense_client_id'),
            'description': '1) سجّل في adsense.google.com بعد نشر الموقع 2) الصق معرف الناشر هنا 3) فعّل الإعلانات'
        }),
        ('🎯 مواضع الوحدات الإعلانية', {
            'fields': ('ad_slot_results', 'ad_slot_recommend_top', 'ad_slot_recommend_bottom'),
            'classes': ('collapse',),
            'description': 'أنشئ وحدات إعلانية (Display ads) في لوحة AdSense والصق أرقامها data-ad-slot هنا — اتركها فارغة لإخفاء الموضع'
        }),
        ('📄 ملف ads.txt', {
            'fields': ('ads_txt',),
            'classes': ('collapse',),
        }),
        ('📊 إحصاءات الزوار Google Analytics', {
            'fields': ('ga4_id', 'ga4_property_id', 'ga_service_account_json'),
            'description': 'GA4 ID: من analytics.google.com (Data Streams). Property ID وفاتح الخدمة: فعّل Analytics Data API في Google Cloud واصنع Service Account بحق Viewer على الخاصية ثم الصق ملف JSON هنا — لعرض عدد الزوار في لوحة الإدارة'
        }),
        ('🤖 الذكاء الاصطناعي (ميزات البحث الأخرى)', {
            'fields': ('deepseek_api_key', 'gemini_api_key', 'groq_api_key'),
            'description': '<b>شكد فلوسك لا يستخدم الذكاء الاصطناعي حالياً</b> ويعتمد فقط على جدول أسعار السوق. هذه المفاتيح تُستخدم لميزات البحث والمواصفات الأخرى: DeepSeek ثم Gemini ثم Groq كحائط صد أخير.'
        }),
        ('💱 سعر الصرف اليدوي', {
            'fields': ('exchange_rate_iqd_per_usd', 'exchange_rate_source'),
            'description': 'هذا السعر يُستخدم لحساب السعر بالدينار أو الدولار عند استيراد أسعار شكد فلوسك إذا كان أحد السعرين ناقصاً.'
        }),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        from django.core.cache import cache
        cache.delete_many(['ga_visitor_stats', 'lookup_data'])
        super().save_model(request, obj, form, change)

    def settings_summary(self, obj):
        if obj.show_ads and obj.adsense_client_id:
            return format_html('<span style="color: #15803d; font-weight:700;">✅ Ads enabled — {}</span>', obj.adsense_client_id)
        if obj.adsense_client_id:
            return mark_safe('<span style="color: #b45309;">⚠️ ID exists but ads disabled</span>')
        return mark_safe('<span style="color: #475569;">⚪ AdSense not linked yet</span>')
    settings_summary.short_description = 'Status'


class SponsorForm(forms.ModelForm):
    password_raw = forms.CharField(
        label='كلمة المرور',
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••'}),
        required=False,
    )

    class Meta:
        model = Sponsor
        fields = ['name', 'slug', 'code_prefix', 'discount', 'website', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ('name', 'code_prefix'):
            if f in self.fields:
                self.fields[f].required = False


@admin.register(Sponsor)
class SponsorAdmin(admin.ModelAdmin):
    form = SponsorForm
    list_display = ('name_preview', 'slug', 'discount_badge', 'codes_count', 'banners_count', 'active_badge')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')
    list_per_page = 25

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _bc=Count('banners', distinct=True),
            _tc=Count('codes', distinct=True),
            _uc=Count('codes', distinct=True, filter=db_models.Q(codes__status='used')),
        )

    fieldsets = (
        ('🔐 بيانات الحساب', {
            'fields': ('name', 'slug', 'code_prefix'),
            'description': 'أدخل الاسم والمعرّف والبادئة.'
        }),
        ('🎁 الخصم', {
            'fields': ('discount',),
        }),
        ('🌐 الموقع الإلكتروني', {
            'fields': ('website',),
        }),
        ('🔑 كلمة المرور', {
            'fields': ('password_raw',),
        }),
        ('⚙️ الحالة', {
            'fields': ('is_active',),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        ro = []
        return ro

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'slug' in form.base_fields:
            form.base_fields['slug'].help_text = 'اسم المستخدم للدخول (إنجليزي فقط) — يُولَّد تلقائياً من الاسم'
        if 'code_prefix' in form.base_fields:
            form.base_fields['code_prefix'].help_text = 'بادئة الكود مثل HISAM — تُولَّد تلقائياً'
        if 'discount' in form.base_fields:
            form.base_fields['discount'].help_text = 'نسبة الخصم %'
        if 'password_raw' in form.base_fields:
            if obj and obj.password:
                form.base_fields['password_raw'].help_text = 'اتركه فارغاً للإبقاء على كلمة المرور الحالية'
            else:
                form.base_fields['password_raw'].help_text = 'مطلوب — تُخزَّن مشفّرة'
        return form

    def save_model(self, request, obj, form, change):
        raw = form.cleaned_data.get('password_raw')
        if raw:
            obj.set_password(raw)
        if not obj.slug:
            import re
            obj.slug = re.sub(r'[^a-z0-9]', '', obj.name.lower().replace(' ', ''))
        if not obj.code_prefix:
            obj.code_prefix = obj.slug.upper()
        super().save_model(request, obj, form, change)

    def name_preview(self, obj):
        return format_html('<b>{}</b>', obj.name)
    name_preview.short_description = 'الشركة'

    def discount_badge(self, obj):
        return format_html('<span style="background:#fef3c7; padding:3px 12px; border-radius:12px; color:#b45309; font-weight:700;">{}%</span>', obj.discount)
    discount_badge.short_description = 'الخصم'

    def codes_count(self, obj):
        total = getattr(obj, '_tc', None)
        used = getattr(obj, '_uc', None)
        if total is None:
            total = obj.codes.count()
        if used is None:
            used = obj.codes.filter(status='used').count()
        color = '#15803d' if used > 0 else '#64748b'
        return format_html('<span style="color:{};">{}/{}</span>', color, used, total)
    codes_count.short_description = 'الأكواد'

    def banners_count(self, obj):
        bc = getattr(obj, '_bc', None)
        if bc is None:
            bc = obj.banners.count()
        return bc
    banners_count.short_description = 'البنرات'

    def active_badge(self, obj):
        if obj.is_active:
            return mark_safe('<span class="badge badge-green">مفعل</span>')
        return mark_safe('<span class="badge badge-red">متوقف</span>')
    active_badge.short_description = 'الحالة'


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'sponsor', 'status_badge', 'created_at', 'used_at', 'verified_by_display')
    list_filter = ('status', 'sponsor')
    search_fields = ('code', 'sponsor__name', 'verified_by')
    date_hierarchy = 'created_at'
    readonly_fields = ('code', 'created_at', 'used_at', 'verified_by')
    list_per_page = 50
    list_select_related = ('sponsor',)

    fieldsets = (
        ('🎟️ الكود', {
            'fields': ('code', 'sponsor'),
            'description': 'الكود يُولَّد تلقائياً ولا يمكن تعديله يدوياً.'
        }),
        ('🔢 الحالة', {
            'fields': ('status',),
        }),
        ('📅 التواريخ', {
            'fields': ('created_at', 'used_at'),
        }),
        ('👤 التحقق', {
            'fields': ('verified_by',),
        }),
    )

    def status_badge(self, obj):
        if obj.status == 'used':
            return mark_safe('<span class="badge badge-red">مستخدم</span>')
        return mark_safe('<span class="badge badge-green">نشط</span>')
    status_badge.short_description = 'الحالة'

    def verified_by_display(self, obj):
        if obj.verified_by:
            return format_html('<span style="color:#1d4ed8;">{}</span>', obj.verified_by)
        return '—'
    verified_by_display.short_description = 'تم التحقق من قبل'


admin.site.index_template = 'admin/custom_index.html'
admin.site.site_header = 'سيارتي · لوحة الإدارة'
admin.site.site_title = 'سيارتي'
admin.site.index_title = 'لوحة التحكم'


DASH_STATS_CACHE_KEY = 'admin_dash_stats'
DASH_STATS_CACHE_TTL = 60


def get_dashboard_stats():
    """إحصاءات لوحة التحكم — تُحسب وتُخزَّن دقيقة كاملة حتى لا تُثقَل كل صفحة إدارة.

    تُمسح تلقائياً بانتهاء الصلاحية (60 ثانية)؛ الأرقام داخل 60 ثانية كافية للوحة.
    """
    from django.core.cache import cache as _cache

    cached = _cache.get(DASH_STATS_CACHE_KEY)
    if cached is not None:
        return cached

    from .services.ga_stats import get_visitor_stats

    sponsors_data = Sponsor.objects.annotate(
        bc=Count('banners'),
        tc=Count('codes'),
        uc=Count('codes', filter=db_models.Q(codes__status='used')),
    ).order_by('name')

    sponsors_table = []
    for s in sponsors_data:
        sponsors_table.append({
            'name': s.name,
            'slug': s.slug,
            'discount': s.discount,
            'banners_count': s.bc,
            'total_codes': s.tc,
            'used_codes': s.uc,
            'is_active': s.is_active,
        })

    banners_table = list(
        AdBanner.objects.select_related('sponsor').order_by('position', 'order', '-created_at').values(
            'id', 'title', 'position', 'order', 'is_active', 'sponsor__name'
        )[:20]
    )
    for b in banners_table:
        b['sponsor_name'] = b.get('sponsor__name') or ''

    recent_codes_qs = PromoCode.objects.select_related('sponsor').order_by('-created_at')[:20]
    recent_codes = []
    for c in recent_codes_qs:
        recent_codes.append({
            'code': c.code,
            'sponsor_name': c.sponsor.name,
            'status': c.status,
            'created_at': c.created_at.strftime('%Y-%m-%d %H:%M') if c.created_at else '',
            'used_at': c.used_at.strftime('%Y-%m-%d %H:%M') if c.used_at else None,
            'verified_by': c.verified_by or '—',
        })

    total_codes = PromoCode.objects.count()
    used_codes = PromoCode.objects.filter(status='used').count()

    result = {
        'total_cars': CarSpecification.objects.count(),
        'total_brands': CarSpecification.objects.values('brand_ar').distinct().count(),
        'total_banners': AdBanner.objects.count(),
        'active_banners': AdBanner.objects.filter(is_active=True).count(),
        'total_sponsors': Sponsor.objects.count(),
        'total_codes': total_codes,
        'used_codes': used_codes,
        'sponsors_table': sponsors_table,
        'banners_table': banners_table,
        'recent_codes': recent_codes,
        'visitor_stats': get_visitor_stats(),
    }
    _cache.set(DASH_STATS_CACHE_KEY, result, DASH_STATS_CACHE_TTL)
    return result


from django.template.context_processors import request as request_processor

def admin_context_processor(request):
    if request.path.startswith('/admin/'):
        return get_dashboard_stats()
    return {}
