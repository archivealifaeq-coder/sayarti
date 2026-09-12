from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import redirect
from django import forms
from django.http import HttpResponse
from django.template import Template, RequestContext
from django.utils.html import format_html, mark_safe
from django.core.cache import cache
from django.db.models import Count, Sum
from django.db import models as db_models
from .models import CarSpecification, AdBanner, FeatureCard, SiteSettings, Sponsor, PromoCode, Dealer, AppInstallMetric, DealerClickMetric
from .services.excel_importer import import_cars_from_excel


class CsvImportForm(forms.Form):
    excel_file = forms.FileField(label="اختر ملف الأكسل")


class CarExportForm(forms.Form):
    brand = forms.ChoiceField(label="الماركة", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        brands = CarSpecification.objects.order_by('brand_ar').values_list('brand_ar', flat=True).distinct()
        self.fields['brand'].choices = [('', 'تصدير كل الماركات')] + [(brand, brand) for brand in brands if brand]


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
        ('🛞 الإطارات', {
            'fields': ('tire_size',)
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
            path('export-excel/', self.admin_site.admin_view(self.export_excel_view), name='car_export_excel'),
        ]
        return custom_urls + urls

    def _export_rows(self, queryset):
        return [
            {
                'id': car.id,
                'Brand_EN': car.brand_en,
                'Brand_AR': car.brand_ar,
                'Model_EN': car.model_en,
                'Model_AR': car.model_ar,
                'Year': car.year,
                'Spec': car.spec or '',
                'Trim': car.trim or '',
                'Engine': car.engine,
                'Oil Visc': car.oil_visc,
                'Oil Visc (>100k)': car.oil_visc_high_km or '',
                'Fuel': car.fuel,
                'Octane': car.octane,
                'Tire Size': car.tire_size,
                'Oil Capacity': car.oil_capacity,
                'Recommendations': car.recommendations or '',
                'Oil Brands': car.oil_brands or '',
                'Battery': car.battery or '',
                'Transmission Type': car.transmission_type or '',
                'Transmission Oil Spec': car.transmission_oil_spec or '',
                'Transmission Oil Brands': car.transmission_oil_brands or '',
            }
            for car in queryset
        ]

    def export_excel_view(self, request):
        form = CarExportForm(request.GET or None)
        if request.GET.get('download') == '1' and form.is_valid():
            brand = form.cleaned_data.get('brand')
            queryset = CarSpecification.objects.order_by('brand_ar', 'model_ar', 'year', 'id')
            if brand:
                queryset = queryset.filter(brand_ar=brand)

            from io import BytesIO
            import pandas as pd

            output = BytesIO()
            df = pd.DataFrame(self._export_rows(queryset))
            if df.empty:
                df = pd.DataFrame(columns=[
                    'id', 'Brand_EN', 'Brand_AR', 'Model_EN', 'Model_AR', 'Year', 'Spec', 'Trim',
                    'Engine', 'Oil Visc', 'Oil Visc (>100k)', 'Fuel', 'Octane', 'Tire Size',
                    'Oil Capacity', 'Recommendations', 'Oil Brands', 'Battery', 'Transmission Type',
                    'Transmission Oil Spec', 'Transmission Oil Brands'
                ])
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='CarSpecifications')
                worksheet = writer.sheets['CarSpecifications']
                worksheet.freeze_panes = 'A2'
                for cell in worksheet[1]:
                    cell.font = cell.font.copy(bold=True)
                for column_cells in worksheet.columns:
                    width = min(max(len(str(cell.value or '')) for cell in column_cells) + 3, 42)
                    worksheet.column_dimensions[column_cells[0].column_letter].width = width
            output.seek(0)

            filename_brand = 'brand' if brand else 'all'
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="car-specifications-{filename_brand}.xlsx"'
            return response

        html_template = """
        {% extends "admin/base_site.html" %}
        {% block content %}
        <div class="section-card" style="max-width: 720px; margin: 20px auto;">
            <h3>📤 تصدير قاعدة بيانات السيارات إلى Excel</h3>
            <p style="color:#475569; line-height:1.9;">اختر ماركة محددة أو اترك الخيار على تصدير كل الماركات. الملف الناتج يستخدم نفس عناوين الأعمدة المطلوبة في الاستيراد الحالي.</p>
            <form method="GET">
                {{ form.as_p }}
                <input type="hidden" name="download" value="1">
                <button type="submit" class="btn btn-primary" style="border:none;">تصدير Excel</button>
                <a href="../" style="color:#64748b; margin-right:10px;">إلغاء</a>
            </form>
        </div>
        {% endblock %}
        """
        t = Template(html_template)
        c = RequestContext(request, {"form": form, "opts": self.model._meta})
        return HttpResponse(t.render(c))

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
            }),
            'subtitle': forms.TextInput(attrs={
                'placeholder': 'مثال: أداء أفضل - توفير في الوقود',
            }),
            'image': forms.FileInput(),
            'image_mobile': forms.FileInput(),
            'background_color': forms.Select(attrs={
            }),
            'button_text': forms.TextInput(attrs={
                'placeholder': 'اعرف المزيد',
            }),
            'button_url': forms.URLInput(attrs={
                'placeholder': 'https://example.com',
            }),
            'order': forms.NumberInput(),
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


@admin.register(Dealer)
class DealerAdmin(admin.ModelAdmin):
    list_display = ('name_display', 'dealer_type_badge', 'parts_region_badge', 'governorate', 'phone', 'is_featured', 'is_active', 'order', 'updated_at')
    list_editable = ('is_featured', 'is_active', 'order')
    list_filter = ('dealer_type', 'parts_region', 'governorate', 'is_featured', 'is_active')
    search_fields = ('name', 'governorate', 'address', 'phone', 'whatsapp', 'brands', 'description')
    ordering = ('dealer_type', 'parts_region', '-is_featured', 'order', 'name')
    list_per_page = 30
    formfield_overrides = {
        db_models.TextField: {'widget': forms.Textarea(attrs={'rows': 4, 'style': 'width: 100%; max-width: 720px;'})},
    }
    fieldsets = (
        ('تصنيف الوكيل', {
            'fields': ('dealer_type', 'parts_region', 'is_active', 'is_featured', 'order'),
            'description': 'اختر وكلاء الزيوت أو وكلاء قطع الغيار. في وكلاء الزيوت يمكن ترك التصنيف عام.'
        }),
        ('معلومات الوكيل', {
            'fields': ('name', 'governorate', 'address', 'brands', 'description')
        }),
        ('التواصل والروابط', {
            'fields': ('phone', 'whatsapp', 'website'),
            'description': 'رقم واتساب يمكن كتابته بصيغة دولية مثل 9647700000000 أو رقم محلي.'
        }),
    )

    def name_display(self, obj):
        featured = ' ⭐' if obj.is_featured else ''
        return format_html('<b>{}{}</b><br><span style="color:#64748b;font-size:.78rem;">{}</span>', obj.name, featured, obj.brands or obj.address or '—')
    name_display.short_description = 'الوكيل'

    def dealer_type_badge(self, obj):
        cls = 'badge-blue' if obj.dealer_type == 'oil' else 'badge-amber'
        return format_html('<span class="badge {}">{}</span>', cls, obj.get_dealer_type_display())
    dealer_type_badge.short_description = 'النوع'

    def parts_region_badge(self, obj):
        return format_html('<span class="badge badge-green">{}</span>', obj.get_parts_region_display())
    parts_region_badge.short_description = 'التصنيف'

@admin.register(AppInstallMetric)
class AppInstallMetricAdmin(admin.ModelAdmin):
    list_display = ('event_display', 'count_display', 'updated_at', 'reset_link')
    readonly_fields = ('event', 'count', 'updated_at')
    actions = ('reset_selected_counters',)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('reset/<int:metric_id>/', self.admin_site.admin_view(self.reset_metric), name='app_install_metric_reset'),
            path('reset-all/', self.admin_site.admin_view(self.reset_all_metrics), name='app_install_metric_reset_all'),
        ]
        return custom_urls + urls

    def has_add_permission(self, request):
        return False

    def event_display(self, obj):
        return obj.get_event_display()
    event_display.short_description = 'الحدث'

    def count_display(self, obj):
        return format_html('<b>{}</b>', f'{obj.count:,}')
    count_display.short_description = 'العدد'

    def reset_selected_counters(self, request, queryset):
        updated = queryset.update(count=0)
        self.message_user(request, f'تم تصفير {updated} عداد.', messages.SUCCESS)
    reset_selected_counters.short_description = 'تصفير العدادات المحددة'

    def reset_link(self, obj):
        return format_html('<a class="button" href="reset/{}/">تصفير</a>', obj.pk)
    reset_link.short_description = 'تصفير مفرد'

    def reset_metric(self, request, metric_id):
        AppInstallMetric.objects.filter(pk=metric_id).update(count=0)
        cache.delete('admin_dash_stats')
        self.message_user(request, 'تم تصفير العداد.', messages.SUCCESS)
        return redirect('../../')

    def reset_all_metrics(self, request):
        AppInstallMetric.objects.update(count=0)
        cache.delete('admin_dash_stats')
        self.message_user(request, 'تم تصفير كل عدادات تثبيت التطبيق.', messages.SUCCESS)
        return redirect('../')


@admin.register(DealerClickMetric)
class DealerClickMetricAdmin(admin.ModelAdmin):
    list_display = ('dealer', 'action_display', 'count_display', 'updated_at', 'reset_link')
    list_filter = ('action', 'dealer__dealer_type', 'dealer__parts_region')
    search_fields = ('dealer__name',)
    readonly_fields = ('dealer', 'action', 'count', 'updated_at')
    actions = ('reset_selected_counters',)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('reset/<int:metric_id>/', self.admin_site.admin_view(self.reset_metric), name='dealer_click_metric_reset'),
            path('reset-all/', self.admin_site.admin_view(self.reset_all_metrics), name='dealer_click_metric_reset_all'),
        ]
        return custom_urls + urls

    def has_add_permission(self, request):
        return False

    def action_display(self, obj):
        return obj.get_action_display()
    action_display.short_description = 'نوع النقرة'

    def count_display(self, obj):
        return format_html('<b>{}</b>', f'{obj.count:,}')
    count_display.short_description = 'العدد'

    def reset_selected_counters(self, request, queryset):
        updated = queryset.update(count=0)
        self.message_user(request, f'تم تصفير {updated} عداد.', messages.SUCCESS)
    reset_selected_counters.short_description = 'تصفير العدادات المحددة'

    def reset_link(self, obj):
        return format_html('<a class="button" href="reset/{}/">تصفير</a>', obj.pk)
    reset_link.short_description = 'تصفير مفرد'

    def reset_metric(self, request, metric_id):
        DealerClickMetric.objects.filter(pk=metric_id).update(count=0)
        cache.delete('admin_dash_stats')
        self.message_user(request, 'تم تصفير العداد.', messages.SUCCESS)
        return redirect('../../')

    def reset_all_metrics(self, request):
        DealerClickMetric.objects.update(count=0)
        cache.delete('admin_dash_stats')
        self.message_user(request, 'تم تصفير كل عدادات تواصل الوكلاء.', messages.SUCCESS)
        return redirect('../')

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
        ('🧩 بطاقات الواجهة', {
            'fields': ('show_dealers_card',),
            'description': 'تحكم بظهور بطاقة وكلاء الزيوت وقطع الغيار في الصفحة الرئيسية.'
        }),
        ('📄 ملف ads.txt', {
            'fields': ('ads_txt',),
            'classes': ('collapse',),
        }),
        ('📊 إحصاءات الزوار Google Analytics', {
            'fields': ('ga4_id', 'ga4_property_id', 'ga_service_account_json'),
            'description': 'GA4 ID: من analytics.google.com (Data Streams). Property ID وفاتح الخدمة: فعّل Analytics Data API في Google Cloud واصنع Service Account بحق Viewer على الخاصية ثم الصق ملف JSON هنا — لعرض عدد الزوار في لوحة الإدارة'
        }),
        ('🤖 مفاتيح الذكاء الاصطناعي', {
            'fields': ('deepseek_api_key', 'gemini_api_key', 'groq_api_key'),
            'description': 'هذه المفاتيح تستخدم لميزات البحث الذكي فقط.'
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
    install_counts = {item['event']: item['count'] for item in AppInstallMetric.objects.values('event', 'count')}
    dealer_click_total = DealerClickMetric.objects.aggregate(total=Sum('count'))['total'] or 0
    dealer_clicks_table = list(
        DealerClickMetric.objects.select_related('dealer')
        .order_by('-count', 'dealer__name')
        .values('dealer__name', 'dealer__dealer_type', 'action', 'count')[:20]
    )
    for item in dealer_clicks_table:
        item['dealer_name'] = item.get('dealer__name') or ''
        item['dealer_type'] = 'زيوت' if item.get('dealer__dealer_type') == 'oil' else 'قطع غيار'
        item['action_label'] = dict(DealerClickMetric.ACTION_CHOICES).get(item['action'], item['action'])

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
        'app_install_prompt_clicks': install_counts.get('prompt_click', 0),
        'app_install_done': install_counts.get('installed', 0),
        'dealer_click_total': dealer_click_total,
        'dealer_clicks_table': dealer_clicks_table,
    }
    _cache.set(DASH_STATS_CACHE_KEY, result, DASH_STATS_CACHE_TTL)
    return result


from django.template.context_processors import request as request_processor

def admin_context_processor(request):
    if request.path.startswith('/admin/'):
        return get_dashboard_stats()
    return {}
