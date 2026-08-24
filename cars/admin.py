import pandas as pd
from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import redirect
from django import forms
from django.http import HttpResponse
from django.template import Template, RequestContext
from django.utils.html import format_html
from django.db.models import Count
from .models import CarSpecification, AdBanner, FeatureCard
from .services.excel_importer import import_cars_from_excel


class CsvImportForm(forms.Form):
    excel_file = forms.FileField(label="اختر ملف الأكسل")


# ============================================================
# ✅ إدارة مواصفات السيارات (CarSpecification)
# ============================================================
@admin.register(CarSpecification)
class CarSpecificationAdmin(admin.ModelAdmin):
    # ✅ ربط قالب قائمة العرض المخصص (يضيف زر استيراد Excel)
    change_list_template = 'admin/cars_changelist.html'

    # ✅ ترتيب الحقول في قائمة العرض
    list_display = (
        'id', 
        'brand_ar_display', 
        'model_ar_display', 
        'year_display', 
        'engine_type_badge', 
        'spec_region_badge', 
        'octane_display', 
        'tire_size_display'
    )
    
    # ✅ روابط سريعة
    list_display_links = ('id', 'brand_ar_display', 'model_ar_display')
    
    # ✅ الفلاتر الجانبية
    list_filter = (
        'brand_ar', 
        'year', 
        'engine_type', 
        'spec_region', 
        'octane'
    )
    
    # ✅ حقول البحث
    search_fields = (
        'brand_ar', 
        'brand_en', 
        'model_ar', 
        'model_en', 
        'id', 
        'tire_size'
    )
    
    # ✅ ترتيب النتائج الافتراضي
    ordering = ('brand_ar', 'model_ar', '-year')
    
    # ✅ عدد العناصر في الصفحة
    list_per_page = 25
    
    # ✅ الإجراءات السريعة (Actions)
    actions = ['make_gcc_spec', 'make_american_spec', 'make_european_spec', 'delete_selected']
    
    # ✅ تقسيم الحقول إلى مجموعات في صفحة الإضافة/التعديل
    fieldsets = (
        ('📋 المعلومات الأساسية', {
            'fields': ('id', 'brand_ar', 'brand_en', 'model_ar', 'model_en', 'year', 'spec')
        }),
        ('⚙️ المحرك والمواصفات', {
            'fields': ('engine', 'engine_type', 'spec_region')
        }),
        ('🛢️ الزيت', {
            'fields': ('oil_visc', 'oil_visc_high_km', 'oil_capacity', 'oil_brands')
        }),
        ('⛽ الوقود', {
            'fields': ('fuel', 'octane')
        }),
        ('🛞 الإطارات والشمعات', {
            'fields': ('tire_size', 'spark')
        }),
        ('📝 توصيات إضافية', {
            'fields': ('recommendations',),
            'classes': ('collapse',)  # ✅ قابلة للطي
        }),
    )

    # ============================================================
    # ✅ عرض محسّن للقائمة
    # ============================================================
    
    def brand_ar_display(self, obj):
        return format_html('<span style="font-weight: bold; color: #fbbf24;">{}</span>', obj.brand_ar)
    brand_ar_display.short_description = 'الماركة'
    
    def model_ar_display(self, obj):
        return format_html('<span style="color: #e2e8f0;">{}</span>', obj.model_ar)
    model_ar_display.short_description = 'الموديل'
    
    def year_display(self, obj):
        return format_html('<span style="background: #1e293b; padding: 2px 10px; border-radius: 12px; color: #60a5fa;">{}</span>', obj.year)
    year_display.short_description = 'السنة'
    
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

    # ============================================================
    # ✅ الإجراءات السريعة (Actions)
    # ============================================================
    
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

    # ============================================================
    # ✅ استيراد Excel (مدمج)
    # ============================================================
    
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
                            
                except Exception as e:
                    self.message_user(request, f"خطأ غير متوقع: {str(e)}", messages.ERROR)
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


# ============================================================
# ✅ إدارة البنرات الإعلانية (AdBanner)
# ============================================================
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

    # ✅ ترتيب أفضل للقائمة
    list_display = (
        'title_preview', 
        'position_badge', 
        'order',              # ✅ اسم الحقل الأصلي
        'is_active',          # ✅ اسم الحقل الأصلي
        'created_at_display'
    )
    
    list_editable = ('order', 'is_active')  # ✅ الآن يتطابق مع list_display
    list_filter = ('position', 'is_active')
    search_fields = ('title', 'button_text')
    ordering = ('position', 'order', '-created_at')
    list_per_page = 20

    # ✅ تنظيم حقول الإضافة
    fieldsets = (
        ('📝 المحتوى', {
            'fields': ('title', 'subtitle', 'position')
        }),
        ('🖼️ الصور', {
            'fields': ('image', 'image_mobile'),
            'description': '📸 سطح المكتب: 1400×500 بكسل | 📱 الهاتف: 800×800 بكسل'
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

    # ============================================================
    # ✅ عرض محسّن للقائمة
    # ============================================================
    
    def title_preview(self, obj):
        icon = '📢' if obj.position == 'ticker' else '🎠'
        color = '#fbbf24' if obj.is_active else '#64748b'
        return format_html('<span style="color: {};">{} {}</span>', color, icon, obj.title[:40])
    title_preview.short_description = 'العنوان'
    
    def position_badge(self, obj):
        if obj.position == 'ticker':
            return format_html('<span style="background: #3b82f620; padding: 2px 12px; border-radius: 12px; color: #60a5fa;">📢 شريط متحرك</span>')
        return format_html('<span style="background: #f59e0b20; padding: 2px 12px; border-radius: 12px; color: #fbbf24;">🎠 سلايدر</span>')
    position_badge.short_description = 'الموقع'
    
    def created_at_display(self, obj):
        return format_html('<span style="color: #64748b; font-size: 0.8rem;">{}</span>', obj.created_at.strftime('%Y-%m-%d %H:%M'))
    created_at_display.short_description = 'تاريخ الإضافة'

    # ============================================================
    # ✅ تحسين واجهة اختيار الألوان
    # ============================================================
    
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
        form.base_fields['image'].help_text = '🖼️ الأبعاد الموصى بها: 1920 × 640 بكسل (عرض كامل - نسبة 3:1)'
        form.base_fields['image_mobile'].help_text = '📱 الأبعاد الموصى بها: 1000 × 750 بكسل (نسبة 4:3)'
        return form


# ============================================================
# ✅ إدارة بطاقات المميزات القابلة للتعديل + الإعلانات
# ============================================================
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
            return format_html('<span style="background: #ef444420; padding: 2px 12px; border-radius: 12px; color: #f87171;">📢 إعلان</span>')
        return format_html('<span style="background: #22c55e20; padding: 2px 12px; border-radius: 12px; color: #4ade80;">⭐ مميزة</span>')
    type_badge.short_description = 'النوع'

    def created_at_display(self, obj):
        return format_html('<span style="color: #64748b; font-size: 0.8rem;">{}</span>', obj.created_at.strftime('%Y-%m-%d'))
    created_at_display.short_description = 'التاريخ'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['icon'].help_text = '🚗 🔧 🧮 ⭐ 💧 🛢️ ⚡ — اتركه فارغاً عند استخدام صورة'
        return form


# ============================================================
# ✅ لوحة التحكم الرئيسية - إحصائيات سريعة
# ============================================================

# ✅ تغيير قالب لوحة التحكم الرئيسية
admin.site.index_template = 'admin/custom_index.html'


# ✅ دالة لإضافة الإحصائيات إلى سياق لوحة التحكم
def get_dashboard_stats():
    return {
        'total_cars': CarSpecification.objects.count(),
        'total_brands': CarSpecification.objects.values('brand_ar').distinct().count(),
        'total_banners': AdBanner.objects.count(),
        'active_banners': AdBanner.objects.filter(is_active=True).count(),
    }


# ✅ إضافة السياق إلى لوحة التحكم
from django.template.context_processors import request as request_processor

def admin_context_processor(request):
    if request.path.startswith('/admin/'):
        return get_dashboard_stats()
    return {}