import pandas as pd
from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import redirect
from django import forms
from django.http import HttpResponse
from django.template import Template, RequestContext
from django.utils.html import format_html, mark_safe
from django.db.models import Count
from .models import CarSpecification, AdBanner, FeatureCard, SiteSettings, Sponsor, PromoCode
from .services.excel_importer import import_cars_from_excel


class CsvImportForm(forms.Form):
    excel_file = forms.FileField(label="اختر ملف الأكسل")


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
        'octane_display', 
        'tire_size_display'
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
    
    list_per_page = 25
    
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
        return format_html('<span style="font-weight: bold; color: #fbbf24;">{}</span>', obj.brand_ar)
    brand_ar_display.short_description = 'الماركة'
    
    def model_ar_display(self, obj):
        return format_html('<span style="color: #e2e8f0;">{}</span>', obj.model_ar)
    model_ar_display.short_description = 'الموديل'
    
    def year_display(self, obj):
        return format_html('<span style="background: #1e293b; padding: 2px 10px; border-radius: 12px; color: #60a5fa;">{}</span>', obj.year)
    year_display.short_description = 'السنة'

    def trim_display(self, obj):
        if obj.trim:
            return format_html('<span style="color: #f472b6; font-weight: bold;">{}</span>', obj.trim)
        return mark_safe('<span style="color: #64748b;">—</span>')
    trim_display.short_description = 'الفئة (Trim)'
    
    def octane_display(self, obj):
        return format_html('<span style="background: rgba(245, 158, 11, 0.15); padding: 2px 12px; border-radius: 12px; color: #fbbf24; font-weight: bold;">{}</span>', obj.octane)
    octane_display.short_description = 'الأوكتان'
    
    def tire_size_display(self, obj):
        return format_html('<span style="color: #60a5fa;">{}</span>', obj.tire_size or 'غير محدد')
    tire_size_display.short_description = 'حجم الإطار'
    
    def engine_type_badge(self, obj):
        colors = {
            'regular': '#94a3b8',
            'hybrid': '#34d399',
            'turbo': '#f87171',
            'diesel': '#fbbf24',
            'electric': '#60a5fa',
        }
        color = colors.get(obj.engine_type, '#94a3b8')
        return format_html('<span style="background: {}20; padding: 2px 12px; border-radius: 12px; color: {}; font-size: 0.8rem;">{}</span>', 
                          color, color, obj.get_engine_type_display())
    engine_type_badge.short_description = 'نوع المحرك'
    
    def spec_region_badge(self, obj):
        colors = {
            'gcc': '#34d399',
            'american': '#60a5fa',
            'european': '#fbbf24',
            'japanese': '#f472b6',
            'chinese': '#f87171',
            'other': '#94a3b8',
        }
        color = colors.get(obj.spec_region, '#94a3b8')
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
        <div style="max-width: 600px; margin: 40px auto; background: #fff; padding: 30px; border-radius: 8px; direction: rtl; text-align: right;">
            <h2>📊 استيراد بيانات السيارات</h2>
            <form method="POST" enctype="multipart/form-data">
                {% csrf_token %}
                {{ form.as_p }}
                <button type="submit" style="background: #417690; color: white; padding: 10px 20px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer;">رفع الملف 🚀</button>
                <a href="../" style="color: #666; margin-right: 10px;">إلغاء</a>
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
        'order',
        'is_active',
        'created_at_display'
    )
    
    list_editable = ('order', 'is_active')
    list_filter = ('position', 'is_active')
    search_fields = ('title', 'button_text')
    ordering = ('position', 'order', '-created_at')
    list_per_page = 20

    fieldsets = (
        ('📝 المحتوى', {
            'fields': ('title', 'subtitle', 'position')
        }),
        ('🎟️ ربط كود الخصم (اختياري)', {
            'fields': ('sponsor',),
            'description': 'اختر شركة راعية ليظهر زر «احصل على خصم» في هذا الإعلان. اتركه فارغاً لبنر عادي بدون خصم.'
        }),
        ('🖼️ الصور', {
            'fields': ('image', 'image_mobile'),
            'description': '📸 سطح المكتب: 1920×820 بكسل (21:9) | 📱 الهاتف: 800×600 بكسل (4:3)'
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
        color = '#fbbf24' if obj.is_active else '#64748b'
        return format_html('<span style="color: {};">{} {}</span>', color, icon, obj.title[:40])
    title_preview.short_description = 'العنوان'
    
    def position_badge(self, obj):
        if obj.position == 'ticker':
            return mark_safe('<span style="background: #3b82f620; padding: 2px 12px; border-radius: 12px; color: #60a5fa;">📢 شريط متحرك</span>')
        return mark_safe('<span style="background: #f59e0b20; padding: 2px 12px; border-radius: 12px; color: #fbbf24;">🎠 سلايدر</span>')
    position_badge.short_description = 'الموقع'
    
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
            'fields': ('image', 'link'),
            'description': '📸 ضع صورة لتتحول البطاقة إلى إعلان، وأضف رابطاً لتصبح قابلة للنقر. الأبعاد الموصى بها: 400×400 بكسل'
        }),
        ('⚙️ الإعدادات', {
            'fields': ('order', 'is_active')
        }),
    )

    def card_preview(self, obj):
        color = '#fbbf24' if obj.is_active else '#64748b'
        icon = obj.icon or '🖼️'
        return format_html('<span style="color: {};">{} <b>{}</b></span>', color, icon, obj.title[:40])
    card_preview.short_description = 'البطاقة'

    def type_badge(self, obj):
        if obj.image:
            return mark_safe('<span style="background: #ef444420; padding: 2px 12px; border-radius: 12px; color: #f87171;">📢 إعلان</span>')
        return mark_safe('<span style="background: #22c55e20; padding: 2px 12px; border-radius: 12px; color: #4ade80;">⭐ مميزة</span>')
    type_badge.short_description = 'النوع'

    def created_at_display(self, obj):
        return format_html('<span style="color: #64748b; font-size: 0.8rem;">{}</span>', obj.created_at.strftime('%Y-%m-%d'))
    created_at_display.short_description = 'التاريخ'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['icon'].help_text = '🚗 🔧 🧮 ⭐ 💧 🛢️ ⚡ — اتركه فارغاً عند استخدام صورة'
        return form


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
        ('🤖 الذكاء الاصطناعي (شكد فلوسك)', {
            'fields': ('groq_api_key', 'gemini_api_key', 'deepseek_api_key'),
            'description': '<b>Groq (الأساسي)</b>: مجاني بدون بطاقة من console.groq.com — <b>Gemini (الاحتياطي)</b>: من aistudio.google.com — <b>DeepSeek</b>: احتياطي اختياري من platform.deepseek.com. بدون مفتاح Groq تظهر رسالة "غير مفعلة".'
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
            return format_html('<span style="color: #4ade80;">✅ Ads enabled — {}</span>', obj.adsense_client_id)
        if obj.adsense_client_id:
            return mark_safe('<span style="color: #fbbf24;">⚠️ ID exists but ads disabled</span>')
        return mark_safe('<span style="color: #64748b;">⚪ AdSense not linked yet</span>')
    settings_summary.short_description = 'Status'


class SponsorForm(forms.ModelForm):
    password_raw = forms.CharField(
        label='كلمة المرور',
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••'}),
        required=False,
    )

    class Meta:
        model = Sponsor
        fields = ['name', 'slug', 'code_prefix', 'discount', 'website', 'password', 'is_active', 'password_raw']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ('name', 'code_prefix', 'website'):
            if f in self.fields:
                self.fields[f].required = False


@admin.register(Sponsor)
class SponsorAdmin(admin.ModelAdmin):
    form = SponsorForm
    list_display = ('name_preview', 'slug', 'discount_badge', 'codes_count', 'active_badge', 'has_password_badge')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')
    readonly_fields = ('name', 'slug', 'code_prefix', 'created_at', 'last_login_display')
    list_per_page = 25

    fieldsets = (
        ('🔐 حساب الشركة الراعية', {
            'fields': ('slug', 'password_raw', 'discount', 'name', 'code_prefix', 'is_active'),
            'description': 'اكتب هنا اسم المستخدم وكلمة المرور ونسبة الخصم — تعرّف كل هذه البيانات بنفسك.'
        }),
        ('📋 أخرى', {
            'fields': ('website', 'created_at', 'last_login_display'),
            'classes': ('collapse',),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        return ('created_at', 'last_login_display', 'password')

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'slug' in form.base_fields:
            form.base_fields['slug'].help_text = 'اسم المستخدم الذي يدخله الراعي في صفحة الدخول (أحرف إنجليزية فقط)'
        if 'discount' in form.base_fields:
            form.base_fields['discount'].help_text = 'نسبة الخصم التي يحصل عليها الزائر'
        if 'password_raw' in form.base_fields:
            if obj and obj.password:
                form.base_fields['password_raw'].help_text = 'اتركه فارغاً للإبقاء على كلمة المرور الحالية'
            else:
                form.base_fields['password_raw'].help_text = 'مطلوب — تُخزَّن مشفّرة ولا تُعرض مرة أخرى'
        return form

    def save_model(self, request, obj, form, change):
        raw = form.cleaned_data.get('password_raw')
        if raw:
            obj.set_password(raw)
        if not obj.name:
            obj.name = obj.slug
        if not obj.code_prefix:
            obj.code_prefix = obj.slug.upper()
        super().save_model(request, obj, form, change)

    def name_preview(self, obj):
        return format_html('<span style="font-weight:700;">{}</span>', obj.name)
    name_preview.short_description = 'الشركة'

    def discount_badge(self, obj):
        return format_html('<span style="background:#fbbf2420; padding:3px 12px; border-radius:12px; color:#fbbf24; font-weight:700;">{}%</span>', obj.discount)
    discount_badge.short_description = 'الخصم'

    def codes_count(self, obj):
        total = obj.codes.count()
        used = obj.codes.filter(status='used').count()
        color = '#4ade80' if used > 0 else '#64748b'
        return format_html('<span style="color:{};">{}/{} </span>', color, used, total)
    codes_count.short_description = 'الأكواد (مستخدمة/الكل)'

    def active_badge(self, obj):
        if obj.is_active:
            return mark_safe('<span style="background:#22c55e20; padding:3px 10px; border-radius:12px; color:#4ade80;">✅ مفعل</span>')
        return mark_safe('<span style="background:#ef444420; padding:3px 10px; border-radius:12px; color:#f87171;">❌ متوقف</span>')
    active_badge.short_description = 'الحالة'

    def has_password_badge(self, obj):
        if obj.password:
            return mark_safe('<span style="color:#4ade80;">✔️</span>')
        return mark_safe('<span style="color:#f87171;">✖️</span>')
    has_password_badge.short_description = 'السجل'

    def last_login_display(self, obj):
        codes = obj.codes.order_by('-used_at').filter(status='used').first()
        if codes and codes.used_at:
            return format_html('<span style="color:#94a3b8;">{}</span>', codes.used_at.strftime('%Y-%m-%d %H:%M'))
        return mark_safe('<span style="color:#475569;">لم يتحقق بعد</span>')
    last_login_display.short_description = 'آخر تحقق'


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'sponsor', 'status_badge', 'created_at', 'used_at')
    list_filter = ('status', 'sponsor')
    search_fields = ('code', 'sponsor__name')
    date_hierarchy = 'created_at'
    readonly_fields = ('code', 'created_at', 'used_at')
    list_per_page = 50

    def status_badge(self, obj):
        if obj.status == 'used':
            return format_html('<span style="background:#ef444420; padding:2px 12px; border-radius:12px; color:#f87171;">مستخدم</span>')
        return format_html('<span style="background:#22c55e20; padding:2px 12px; border-radius:12px; color:#4ade80;">نشط</span>')
    status_badge.short_description = 'الحالة'


admin.site.index_template = 'admin/custom_index.html'


def get_dashboard_stats():
    from .services.ga_stats import get_visitor_stats
    return {
        'total_cars': CarSpecification.objects.count(),
        'total_brands': CarSpecification.objects.values('brand_ar').distinct().count(),
        'total_banners': AdBanner.objects.count(),
        'active_banners': AdBanner.objects.filter(is_active=True).count(),
        'visitor_stats': get_visitor_stats(),
    }


from django.template.context_processors import request as request_processor

def admin_context_processor(request):
    if request.path.startswith('/admin/'):
        return get_dashboard_stats()
    return {}
