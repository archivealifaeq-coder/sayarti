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
from .models import CarSpecification, AdBanner, FeatureCard, SiteSettings, Sponsor, PromoCode
from .services.excel_importer import import_cars_from_excel


class CsvImportForm(forms.Form):
    excel_file = forms.FileField(label="Ø§Ø®ØªØ± Ù…Ù„Ù Ø§Ù„Ø£ÙƒØ³Ù„")


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
        ('ðŸ“‹ Ø§Ù„Ù…Ø¹Ù„ÙˆÙ…Ø§Øª Ø§Ù„Ø£Ø³Ø§Ø³ÙŠØ©', {
            'fields': ('id', 'brand_ar', 'brand_en', 'model_ar', 'model_en', 'year', 'trim', 'spec')
        }),
        ('âš™ï¸ Ø§Ù„Ù…Ø­Ø±Ùƒ ÙˆØ§Ù„Ù…ÙˆØ§ØµÙØ§Øª', {
            'fields': ('engine', 'engine_type', 'spec_region')
        }),
        ('ðŸ›¢ï¸ Ø§Ù„Ø²ÙŠØª', {
            'fields': ('oil_visc', 'oil_visc_high_km', 'oil_capacity', 'oil_brands')
        }),
        ('âš¡ Ø§Ù„Ø¨Ø·Ø§Ø±ÙŠØ© ÙˆÙ†Ø§Ù‚Ù„ Ø§Ù„Ø­Ø±ÙƒØ©', {
            'fields': ('battery', 'transmission_type', 'transmission_oil_spec', 'transmission_oil_brands')
        }),
        ('â›½ Ø§Ù„ÙˆÙ‚ÙˆØ¯', {
            'fields': ('fuel', 'octane')
        }),
        ('ðŸ›ž Ø§Ù„Ø¥Ø·Ø§Ø±Ø§Øª ÙˆØ§Ù„Ø´Ù…Ø¹Ø§Øª', {
            'fields': ('tire_size', 'spark')
        }),
        ('ðŸ“ ØªÙˆØµÙŠØ§Øª Ø¥Ø¶Ø§ÙÙŠØ©', {
            'fields': ('recommendations',),
            'classes': ('collapse',)
        }),
    )
    
    def brand_ar_display(self, obj):
        return format_html('<span style="font-weight: bold; color: #b45309;">{}</span>', obj.brand_ar)
    brand_ar_display.short_description = 'Ø§Ù„Ù…Ø§Ø±ÙƒØ©'
    
    def model_ar_display(self, obj):
        return format_html('<span style="color: #1e293b; font-weight:600;">{}</span>', obj.model_ar)
    model_ar_display.short_description = 'Ø§Ù„Ù…ÙˆØ¯ÙŠÙ„'
    
    def year_display(self, obj):
        return format_html('<span style="background:#dbeafe; padding:2px 10px; border-radius:12px; color:#1d4ed8; font-weight:700;">{}</span>', obj.year)
    year_display.short_description = 'Ø§Ù„Ø³Ù†Ø©'

    def trim_display(self, obj):
        if obj.trim:
            return format_html('<span style="color: #db2777; font-weight: bold;">{}</span>', obj.trim)
        return mark_safe('<span style="color: #64748b;">â€”</span>')
    trim_display.short_description = 'Ø§Ù„ÙØ¦Ø© (Trim)'
    
    def octane_display(self, obj):
        return format_html('<span style="background:#fef3c7; padding:2px 12px; border-radius:12px; color:#b45309; font-weight:bold;">{}</span>', obj.octane)
    octane_display.short_description = 'Ø§Ù„Ø£ÙˆÙƒØªØ§Ù†'
    
    def tire_size_display(self, obj):
        return format_html('<span style="color: #1d4ed8; font-weight:600;">{}</span>', obj.tire_size or 'ØºÙŠØ± Ù…Ø­Ø¯Ø¯')
    tire_size_display.short_description = 'Ø­Ø¬Ù… Ø§Ù„Ø¥Ø·Ø§Ø±'
    
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
    engine_type_badge.short_description = 'Ù†ÙˆØ¹ Ø§Ù„Ù…Ø­Ø±Ùƒ'
    
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
    spec_region_badge.short_description = 'Ø§Ù„Ù…ÙˆØ§ØµÙØ§Øª'
    
    def make_gcc_spec(self, request, queryset):
        updated = queryset.update(spec_region='gcc')
        self.message_user(request, f'âœ… ØªÙ… ØªØ­Ø¯ÙŠØ« {updated} Ø³ÙŠØ§Ø±Ø© Ø¥Ù„Ù‰ Ù…ÙˆØ§ØµÙØ§Øª Ø®Ù„ÙŠØ¬ÙŠØ©', messages.SUCCESS)
    make_gcc_spec.short_description = 'ðŸŒ ØªØºÙŠÙŠØ± Ø§Ù„Ù…ÙˆØ§ØµÙØ§Øª Ø¥Ù„Ù‰ Ø®Ù„ÙŠØ¬ÙŠ'
    
    def make_american_spec(self, request, queryset):
        updated = queryset.update(spec_region='american')
        self.message_user(request, f'âœ… ØªÙ… ØªØ­Ø¯ÙŠØ« {updated} Ø³ÙŠØ§Ø±Ø© Ø¥Ù„Ù‰ Ù…ÙˆØ§ØµÙØ§Øª Ø£Ù…Ø±ÙŠÙƒÙŠØ©', messages.SUCCESS)
    make_american_spec.short_description = 'ðŸŒ ØªØºÙŠÙŠØ± Ø§Ù„Ù…ÙˆØ§ØµÙØ§Øª Ø¥Ù„Ù‰ Ø£Ù…Ø±ÙŠÙƒÙŠ'
    
    def make_european_spec(self, request, queryset):
        updated = queryset.update(spec_region='european')
        self.message_user(request, f'âœ… ØªÙ… ØªØ­Ø¯ÙŠØ« {updated} Ø³ÙŠØ§Ø±Ø© Ø¥Ù„Ù‰ Ù…ÙˆØ§ØµÙØ§Øª Ø£ÙˆØ±ÙˆØ¨ÙŠØ©', messages.SUCCESS)
    make_european_spec.short_description = 'ðŸŒ ØªØºÙŠÙŠØ± Ø§Ù„Ù…ÙˆØ§ØµÙØ§Øª Ø¥Ù„Ù‰ Ø£ÙˆØ±ÙˆØ¨ÙŠ'
    
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
                        success_msg = f"âœ… ØªÙ… Ø§Ù„Ø§Ø³ØªÙŠØ±Ø§Ø¯ Ø¨Ù†Ø¬Ø§Ø­! Ø¥Ø¶Ø§ÙØ© {result['created']} ÙˆØªØ­Ø¯ÙŠØ« {result['updated']}."
                        if result['failed'] > 0:
                            success_msg += f" âŒ ÙØ´Ù„ {result['failed']} ØµÙ."
                            for failed_row in result['failed_rows'][:5]:
                                self.message_user(request, f"âš ï¸ Ø§Ù„ØµÙ {failed_row['row_number']}: {failed_row['error']}", messages.WARNING)
                        self.message_user(request, success_msg, messages.SUCCESS)
                    else:
                        for error in result['errors']:
                            self.message_user(request, f"âŒ {error}", messages.ERROR)
                            
                except Exception:
                    import logging
                    logging.getLogger('cars').exception('Admin Excel import failed')
                    self.message_user(request, "âŒ Ø­Ø¯Ø« Ø®Ø·Ø£ ØºÙŠØ± Ù…ØªÙˆÙ‚Ø¹ Ø£Ø«Ù†Ø§Ø¡ Ø§Ù„Ø§Ø³ØªÙŠØ±Ø§Ø¯. Ø±Ø§Ø¬Ø¹ Ø§Ù„Ø³Ø¬Ù„Ø§Øª.", messages.ERROR)
            else:
                self.message_user(request, "Ù„Ù… ÙŠØªÙ… Ø§Ø®ØªÙŠØ§Ø± Ù…Ù„Ù.", messages.WARNING)
            
            return redirect("..")

        form = CsvImportForm()
        html_template = """
        {% extends "admin/base_site.html" %}
        {% block content %}
        <div class="section-card" style="max-width: 600px; margin: 20px auto;">
            <h3>ðŸ“Š Ø§Ø³ØªÙŠØ±Ø§Ø¯ Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø³ÙŠØ§Ø±Ø§Øª</h3>
            <form method="POST" enctype="multipart/form-data">
                {% csrf_token %}
                {{ form.as_p }}
                <button type="submit" class="btn btn-primary" style="border:none;">Ø±ÙØ¹ Ø§Ù„Ù…Ù„Ù ðŸš€</button>
                <a href="../" style="color:#64748b; margin-right:10px;">Ø¥Ù„ØºØ§Ø¡</a>
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
                'placeholder': 'Ù…Ø«Ø§Ù„: Ø®ØµÙ… 20% Ø¹Ù„Ù‰ Ø²ÙŠØª Ø§Ù„Ù…Ø­Ø±Ùƒ',
                'style': 'width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #ddd;'
            }),
            'subtitle': forms.TextInput(attrs={
                'placeholder': 'Ù…Ø«Ø§Ù„: Ø£Ø¯Ø§Ø¡ Ø£ÙØ¶Ù„ - ØªÙˆÙÙŠØ± ÙÙŠ Ø§Ù„ÙˆÙ‚ÙˆØ¯',
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
                'placeholder': 'Ø§Ø¹Ø±Ù Ø§Ù„Ù…Ø²ÙŠØ¯',
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
        ('ðŸ“ Ø§Ù„Ù…Ø­ØªÙˆÙ‰', {
            'fields': ('title', 'subtitle', 'position')
        }),
        ('ðŸŽŸï¸ Ø±Ø¨Ø· ÙƒÙˆØ¯ Ø§Ù„Ø®ØµÙ… (Ø§Ø®ØªÙŠØ§Ø±ÙŠ)', {
            'fields': ('sponsor',),
            'description': 'Ø§Ø®ØªØ± Ø´Ø±ÙƒØ© Ø±Ø§Ø¹ÙŠØ© Ù„ÙŠØ¸Ù‡Ø± Ø²Ø± Â«Ø§Ø­ØµÙ„ Ø¹Ù„Ù‰ Ø®ØµÙ…Â» ÙÙŠ Ù‡Ø°Ø§ Ø§Ù„Ø¥Ø¹Ù„Ø§Ù†. Ø§ØªØ±ÙƒÙ‡ ÙØ§Ø±ØºØ§Ù‹ Ù„Ø¨Ù†Ø± Ø¹Ø§Ø¯ÙŠ Ø¨Ø¯ÙˆÙ† Ø®ØµÙ….',
            'classes': ('collapse',),
        }),
        ('ðŸ–¼ï¸ Ø§Ù„ØµÙˆØ±', {
            'fields': ('image', 'image_mobile'),
            'description': 'ðŸ“¸ Ø³Ø·Ø­ Ø§Ù„Ù…ÙƒØªØ¨: 1920Ã—820 Ø¨ÙƒØ³Ù„ (21:9) | ðŸ“± Ø§Ù„Ù‡Ø§ØªÙ: 800Ã—600 Ø¨ÙƒØ³Ù„ (4:3)',
            'classes': ('collapse',),
        }),
        ('ðŸŽ¨ Ø§Ù„Ø£Ù„ÙˆØ§Ù† (Ø§Ø­ØªÙŠØ§Ø·ÙŠ)', {
            'fields': ('background_color', 'text_color'),
            'classes': ('collapse',)
        }),
        ('ðŸ”— Ø§Ù„Ø±Ø§Ø¨Ø·', {
            'fields': ('button_text', 'button_url')
        }),
        ('âš™ï¸ Ø§Ù„Ø¥Ø¹Ø¯Ø§Ø¯Ø§Øª', {
            'fields': ('order', 'is_active')
        }),
    )
    
    def title_preview(self, obj):
        icon = 'ðŸ“¢' if obj.position == 'ticker' else 'ðŸŽ '
        color = '#b45309' if obj.is_active else '#475569'
        return format_html('<span style="color: {}; font-weight:600;">{} {}</span>', color, icon, obj.title[:40])
    title_preview.short_description = 'Ø§Ù„Ø¹Ù†ÙˆØ§Ù†'
    
    def position_badge(self, obj):
        if obj.position == 'ticker':
            return mark_safe('<span style="background:#dbeafe; padding:2px 12px; border-radius:12px; color:#1d4ed8;">ðŸ“¢ Ø´Ø±ÙŠØ· Ù…ØªØ­Ø±Ùƒ</span>')
        return mark_safe('<span style="background:#fef3c7; padding:2px 12px; border-radius:12px; color:#b45309;">ðŸŽ  Ø³Ù„Ø§ÙŠØ¯Ø±</span>')
    position_badge.short_description = 'Ø§Ù„Ù…ÙˆÙ‚Ø¹'
    
    def sponsor_display(self, obj):
        if obj.sponsor_id:
            return format_html('<span style="background:#ede9fe; padding:2px 12px; border-radius:12px; color:#6d28d9;">ðŸŽŸï¸ {}</span>', obj.sponsor.name)
        return mark_safe('<span style="color:#475569;">â€”</span>')
    sponsor_display.short_description = 'Ø§Ù„Ø´Ø±ÙƒØ©'

    def created_at_display(self, obj):
        return format_html('<span style="color: #64748b; font-size: 0.8rem;">{}</span>', obj.created_at.strftime('%Y-%m-%d %H:%M'))
    created_at_display.short_description = 'ØªØ§Ø±ÙŠØ® Ø§Ù„Ø¥Ø¶Ø§ÙØ©'

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'position':
            kwargs['widget'] = forms.Select(choices=[
                ('ticker', 'ðŸ“¢ Ø´Ø±ÙŠØ· Ù…ØªØ­Ø±Ùƒ Ø¹Ù„ÙˆÙŠ (5%) - Ø£Ø¹Ù„Ù‰ Ø§Ù„ØµÙØ­Ø©'),
                ('slider', 'ðŸŽ  Ø³Ù„Ø§ÙŠØ¯Ø± Ø±Ø¦ÙŠØ³ÙŠ (35%) - ÙˆØ³Ø· Ø§Ù„ØµÙØ­Ø©'),
            ])
        elif db_field.name == 'background_color':
            kwargs['widget'] = forms.Select(choices=[
                ('from-amber-600 via-orange-600 to-red-700', 'ðŸ”¥ Ø¨Ø±ØªÙ‚Ø§Ù„ÙŠ-Ø£Ø­Ù…Ø± (Ù„Ù„Ø´Ø±ÙŠØ·)'),
                ('from-blue-700 via-cyan-600 to-teal-700', 'ðŸŒŠ Ø£Ø²Ø±Ù‚-ÙÙŠØ±ÙˆØ²ÙŠ (Ù„Ù„Ø´Ø±ÙŠØ·)'),
                ('from-purple-700 via-pink-600 to-rose-700', 'ðŸ’— Ø¨Ù†ÙØ³Ø¬ÙŠ-ÙˆØ±Ø¯ÙŠ (Ù„Ù„Ø´Ø±ÙŠØ·)'),
                ('from-green-600 via-emerald-600 to-teal-700', 'ðŸŒ¿ Ø£Ø®Ø¶Ø±-Ø²Ù…Ø±Ø¯ÙŠ (Ù„Ù„Ø´Ø±ÙŠØ·)'),
                ('from-yellow-500 via-amber-500 to-orange-500', 'â­ Ø£ØµÙØ±-Ø¨Ø±ØªÙ‚Ø§Ù„ÙŠ (Ù„Ù„Ø´Ø±ÙŠØ·)'),
                ('from-red-600 via-rose-600 to-pink-600', 'â¤ï¸ Ø£Ø­Ù…Ø±-ÙˆØ±Ø¯ÙŠ (Ù„Ù„Ø´Ø±ÙŠØ·)'),
                ('from-indigo-700 via-purple-700 to-pink-700', 'ðŸ’œ Ù†ÙŠÙ„ÙŠ-Ø¨Ù†ÙØ³Ø¬ÙŠ (Ù„Ù„Ø´Ø±ÙŠØ·)'),
                ('from-blue-700 via-indigo-700 to-purple-700', 'ðŸ’œ Ø£Ø²Ø±Ù‚-Ø¨Ù†ÙØ³Ø¬ÙŠ (Ø³Ù„Ø§ÙŠØ¯Ø±)'),
                ('from-amber-500 via-orange-500 to-red-500', 'ðŸ”¥ Ø¨Ø±ØªÙ‚Ø§Ù„ÙŠ-Ø£Ø­Ù…Ø± (Ø³Ù„Ø§ÙŠØ¯Ø±)'),
                ('from-red-600 via-orange-600 to-yellow-600', 'â¤ï¸ Ø£Ø­Ù…Ø±-Ø£ØµÙØ± (Ø³Ù„Ø§ÙŠØ¯Ø±)'),
                ('from-green-600 via-emerald-600 to-teal-600', 'ðŸŒ¿ Ø£Ø®Ø¶Ø±-ÙÙŠØ±ÙˆØ²ÙŠ (Ø³Ù„Ø§ÙŠØ¯Ø±)'),
                ('from-purple-700 via-pink-600 to-rose-700', 'ðŸ’— Ø¨Ù†ÙØ³Ø¬ÙŠ-ÙˆØ±Ø¯ÙŠ (Ø³Ù„Ø§ÙŠØ¯Ø±)'),
                ('from-cyan-500 via-blue-500 to-indigo-500', 'ðŸŒŠ Ø£Ø²Ø±Ù‚-Ø³Ù…Ø§ÙˆÙŠ (Ø³Ù„Ø§ÙŠØ¯Ø±)'),
                ('from-pink-500 via-rose-500 to-red-500', 'ðŸŒ¸ ÙˆØ±Ø¯ÙŠ-Ø£Ø­Ù…Ø± (Ø³Ù„Ø§ÙŠØ¯Ø±)'),
                ('from-slate-700 via-gray-700 to-zinc-700', 'â¬› Ø±Ù…Ø§Ø¯ÙŠ Ø¯Ø§ÙƒÙ† (Ø³Ù„Ø§ÙŠØ¯Ø±)'),
                ('from-emerald-500 via-teal-500 to-cyan-500', 'ðŸ’š Ø²Ù…Ø±Ø¯ÙŠ-ÙÙŠØ±ÙˆØ²ÙŠ (Ø³Ù„Ø§ÙŠØ¯Ø±)'),
            ])
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj=None, **kwargs)
        form.base_fields['image'].help_text = 'ðŸ–¼ï¸ Ø§Ù„Ø£Ø¨Ø¹Ø§Ø¯ Ø§Ù„Ù…ÙˆØµÙ‰ Ø¨Ù‡Ø§: 1920 Ã— 820 Ø¨ÙƒØ³Ù„ (21:9) â€” Ø§Ù„ØµÙˆØ±Ø© ØªÙÙ‚Øµ ØªÙ„Ù‚Ø§Ø¦ÙŠØ§Ù‹'
        form.base_fields['image_mobile'].help_text = 'ðŸ“± Ø§Ù„Ø£Ø¨Ø¹Ø§Ø¯ Ø§Ù„Ù…ÙˆØµÙ‰ Ø¨Ù‡Ø§: 800 Ã— 600 Ø¨ÙƒØ³Ù„ (4:3)'
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
        ('ðŸ“ Ø§Ù„Ù…Ø­ØªÙˆÙ‰', {
            'fields': ('title', 'description', 'icon')
        }),
        ('ðŸ“¢ Ø¥Ø¹Ù„Ø§Ù† (Ø§Ø®ØªÙŠØ§Ø±ÙŠ)', {
            'fields': ('image', 'link', 'sponsor'),
            'description': 'ðŸ“¸ Ø¶Ø¹ ØµÙˆØ±Ø© Ù„ØªØªØ­ÙˆÙ„ Ø§Ù„Ø¨Ø·Ø§Ù‚Ø© Ø¥Ù„Ù‰ Ø¥Ø¹Ù„Ø§Ù†ØŒ ÙˆØ£Ø¶Ù Ø±Ø§Ø¨Ø·Ø§Ù‹ Ù„ØªØµØ¨Ø­ Ù‚Ø§Ø¨Ù„Ø© Ù„Ù„Ù†Ù‚Ø±. Ø§Ù„Ø£Ø¨Ø¹Ø§Ø¯ Ø§Ù„Ù…ÙˆØµÙ‰ Ø¨Ù‡Ø§: 400Ã—400 Ø¨ÙƒØ³Ù„. ÙˆØ¹Ù†Ø¯ Ø§Ø®ØªÙŠØ§Ø± Ø´Ø±ÙƒØ© Ø±Ø§Ø¹ÙŠØ© ÙŠØ¸Ù‡Ø± ÙÙŠÙ‡Ø§ Ø²Ø± Â«Ø§Ø­ØµÙ„ Ø¹Ù„Ù‰ Ø®ØµÙ…Â».'
        }),
        ('âš™ï¸ Ø§Ù„Ø¥Ø¹Ø¯Ø§Ø¯Ø§Øª', {
            'fields': ('order', 'is_active')
        }),
    )

    def card_preview(self, obj):
        color = '#b45309' if obj.is_active else '#475569'
        icon = obj.icon or 'ðŸ–¼ï¸'
        return format_html('<span style="color: {};">{} <b>{}</b></span>', color, icon, obj.title[:40])
    card_preview.short_description = 'Ø§Ù„Ø¨Ø·Ø§Ù‚Ø©'

    def type_badge(self, obj):
        if obj.image:
            return mark_safe('<span style="background: #fee2e2; padding: 2px 12px; border-radius: 12px; color: #dc2626;">ðŸ“¢ Ø¥Ø¹Ù„Ø§Ù†</span>')
        return mark_safe('<span style="background: #dcfce7; padding: 2px 12px; border-radius: 12px; color: #15803d;">â­ Ù…Ù…ÙŠØ²Ø©</span>')
    type_badge.short_description = 'Ø§Ù„Ù†ÙˆØ¹'

    def created_at_display(self, obj):
        return format_html('<span style="color: #64748b; font-size: 0.8rem;">{}</span>', obj.created_at.strftime('%Y-%m-%d'))
    created_at_display.short_description = 'Ø§Ù„ØªØ§Ø±ÙŠØ®'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['icon'].help_text = 'ðŸš— ðŸ”§ ðŸ§® â­ ðŸ’§ ðŸ›¢ï¸ âš¡ â€” Ø§ØªØ±ÙƒÙ‡ ÙØ§Ø±ØºØ§Ù‹ Ø¹Ù†Ø¯ Ø§Ø³ØªØ®Ø¯Ø§Ù… ØµÙˆØ±Ø©'
        return form


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('settings_summary',)
    fieldsets = (
        ('ðŸ“¢ Ø¥Ø¹Ù„Ø§Ù†Ø§Øª Google AdSense', {
            'fields': ('show_ads', 'adsense_client_id'),
            'description': '1) Ø³Ø¬Ù‘Ù„ ÙÙŠ adsense.google.com Ø¨Ø¹Ø¯ Ù†Ø´Ø± Ø§Ù„Ù…ÙˆÙ‚Ø¹ 2) Ø§Ù„ØµÙ‚ Ù…Ø¹Ø±Ù Ø§Ù„Ù†Ø§Ø´Ø± Ù‡Ù†Ø§ 3) ÙØ¹Ù‘Ù„ Ø§Ù„Ø¥Ø¹Ù„Ø§Ù†Ø§Øª'
        }),
        ('ðŸŽ¯ Ù…ÙˆØ§Ø¶Ø¹ Ø§Ù„ÙˆØ­Ø¯Ø§Øª Ø§Ù„Ø¥Ø¹Ù„Ø§Ù†ÙŠØ©', {
            'fields': ('ad_slot_results', 'ad_slot_recommend_top', 'ad_slot_recommend_bottom'),
            'classes': ('collapse',),
            'description': 'Ø£Ù†Ø´Ø¦ ÙˆØ­Ø¯Ø§Øª Ø¥Ø¹Ù„Ø§Ù†ÙŠØ© (Display ads) ÙÙŠ Ù„ÙˆØ­Ø© AdSense ÙˆØ§Ù„ØµÙ‚ Ø£Ø±Ù‚Ø§Ù…Ù‡Ø§ data-ad-slot Ù‡Ù†Ø§ â€” Ø§ØªØ±ÙƒÙ‡Ø§ ÙØ§Ø±ØºØ© Ù„Ø¥Ø®ÙØ§Ø¡ Ø§Ù„Ù…ÙˆØ¶Ø¹'
        }),
        ('ðŸ“„ Ù…Ù„Ù ads.txt', {
            'fields': ('ads_txt',),
            'classes': ('collapse',),
        }),
        ('ðŸ“Š Ø¥Ø­ØµØ§Ø¡Ø§Øª Ø§Ù„Ø²ÙˆØ§Ø± Google Analytics', {
            'fields': ('ga4_id', 'ga4_property_id', 'ga_service_account_json'),
            'description': 'GA4 ID: Ù…Ù† analytics.google.com (Data Streams). Property ID ÙˆÙØ§ØªØ­ Ø§Ù„Ø®Ø¯Ù…Ø©: ÙØ¹Ù‘Ù„ Analytics Data API ÙÙŠ Google Cloud ÙˆØ§ØµÙ†Ø¹ Service Account Ø¨Ø­Ù‚ Viewer Ø¹Ù„Ù‰ Ø§Ù„Ø®Ø§ØµÙŠØ© Ø«Ù… Ø§Ù„ØµÙ‚ Ù…Ù„Ù JSON Ù‡Ù†Ø§ â€” Ù„Ø¹Ø±Ø¶ Ø¹Ø¯Ø¯ Ø§Ù„Ø²ÙˆØ§Ø± ÙÙŠ Ù„ÙˆØ­Ø© Ø§Ù„Ø¥Ø¯Ø§Ø±Ø©'
        }),
        ('ðŸ¤– Ø§Ù„Ø°ÙƒØ§Ø¡ Ø§Ù„Ø§ØµØ·Ù†Ø§Ø¹ÙŠ (Ø´ÙƒØ¯ ÙÙ„ÙˆØ³Ùƒ)', {
            'fields': ('groq_api_key', 'gemini_api_key', 'deepseek_api_key'),
            'description': '<b>Groq (Ø§Ù„Ø£Ø³Ø§Ø³ÙŠ)</b>: Ù…Ø¬Ø§Ù†ÙŠ Ø¨Ø¯ÙˆÙ† Ø¨Ø·Ø§Ù‚Ø© Ù…Ù† console.groq.com â€” <b>Gemini (Ø§Ù„Ø§Ø­ØªÙŠØ§Ø·ÙŠ)</b>: Ù…Ù† aistudio.google.com â€” <b>DeepSeek</b>: Ø§Ø­ØªÙŠØ§Ø·ÙŠ Ø§Ø®ØªÙŠØ§Ø±ÙŠ Ù…Ù† platform.deepseek.com. Ø¨Ø¯ÙˆÙ† Ù…ÙØªØ§Ø­ Groq ØªØ¸Ù‡Ø± Ø±Ø³Ø§Ù„Ø© "ØºÙŠØ± Ù…ÙØ¹Ù„Ø©".'
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
            return format_html('<span style="color: #15803d; font-weight:700;">âœ… Ads enabled â€” {}</span>', obj.adsense_client_id)
        if obj.adsense_client_id:
            return mark_safe('<span style="color: #b45309;">âš ï¸ ID exists but ads disabled</span>')
        return mark_safe('<span style="color: #475569;">âšª AdSense not linked yet</span>')
    settings_summary.short_description = 'Status'


class SponsorForm(forms.ModelForm):
    password_raw = forms.CharField(
        label='ÙƒÙ„Ù…Ø© Ø§Ù„Ù…Ø±ÙˆØ±',
        widget=forms.PasswordInput(attrs={'placeholder': 'â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢'}),
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
        ('ðŸ” Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø­Ø³Ø§Ø¨', {
            'fields': ('name', 'slug', 'code_prefix'),
            'description': 'Ø£Ø¯Ø®Ù„ Ø§Ù„Ø§Ø³Ù… ÙˆØ§Ù„Ù…Ø¹Ø±Ù‘Ù ÙˆØ§Ù„Ø¨Ø§Ø¯Ø¦Ø©.'
        }),
        ('ðŸŽ Ø§Ù„Ø®ØµÙ…', {
            'fields': ('discount',),
        }),
        ('ðŸŒ Ø§Ù„Ù…ÙˆÙ‚Ø¹ Ø§Ù„Ø¥Ù„ÙƒØªØ±ÙˆÙ†ÙŠ', {
            'fields': ('website',),
        }),
        ('ðŸ”‘ ÙƒÙ„Ù…Ø© Ø§Ù„Ù…Ø±ÙˆØ±', {
            'fields': ('password_raw',),
        }),
        ('âš™ï¸ Ø§Ù„Ø­Ø§Ù„Ø©', {
            'fields': ('is_active',),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        ro = []
        return ro

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'slug' in form.base_fields:
            form.base_fields['slug'].help_text = 'Ø§Ø³Ù… Ø§Ù„Ù…Ø³ØªØ®Ø¯Ù… Ù„Ù„Ø¯Ø®ÙˆÙ„ (Ø¥Ù†Ø¬Ù„ÙŠØ²ÙŠ ÙÙ‚Ø·) â€” ÙŠÙÙˆÙ„ÙŽÙ‘Ø¯ ØªÙ„Ù‚Ø§Ø¦ÙŠØ§Ù‹ Ù…Ù† Ø§Ù„Ø§Ø³Ù…'
        if 'code_prefix' in form.base_fields:
            form.base_fields['code_prefix'].help_text = 'Ø¨Ø§Ø¯Ø¦Ø© Ø§Ù„ÙƒÙˆØ¯ Ù…Ø«Ù„ HISAM â€” ØªÙÙˆÙ„ÙŽÙ‘Ø¯ ØªÙ„Ù‚Ø§Ø¦ÙŠØ§Ù‹'
        if 'discount' in form.base_fields:
            form.base_fields['discount'].help_text = 'Ù†Ø³Ø¨Ø© Ø§Ù„Ø®ØµÙ… %'
        if 'password_raw' in form.base_fields:
            if obj and obj.password:
                form.base_fields['password_raw'].help_text = 'Ø§ØªØ±ÙƒÙ‡ ÙØ§Ø±ØºØ§Ù‹ Ù„Ù„Ø¥Ø¨Ù‚Ø§Ø¡ Ø¹Ù„Ù‰ ÙƒÙ„Ù…Ø© Ø§Ù„Ù…Ø±ÙˆØ± Ø§Ù„Ø­Ø§Ù„ÙŠØ©'
            else:
                form.base_fields['password_raw'].help_text = 'Ù…Ø·Ù„ÙˆØ¨ â€” ØªÙØ®Ø²ÙŽÙ‘Ù† Ù…Ø´ÙÙ‘Ø±Ø©'
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
    name_preview.short_description = 'Ø§Ù„Ø´Ø±ÙƒØ©'

    def discount_badge(self, obj):
        return format_html('<span style="background:#fef3c7; padding:3px 12px; border-radius:12px; color:#b45309; font-weight:700;">{}%</span>', obj.discount)
    discount_badge.short_description = 'Ø§Ù„Ø®ØµÙ…'

    def codes_count(self, obj):
        total = getattr(obj, '_tc', None)
        used = getattr(obj, '_uc', None)
        if total is None:
            total = obj.codes.count()
        if used is None:
            used = obj.codes.filter(status='used').count()
        color = '#15803d' if used > 0 else '#64748b'
        return format_html('<span style="color:{};">{}/{}</span>', color, used, total)
    codes_count.short_description = 'Ø§Ù„Ø£ÙƒÙˆØ§Ø¯'

    def banners_count(self, obj):
        bc = getattr(obj, '_bc', None)
        if bc is None:
            bc = obj.banners.count()
        return bc
    banners_count.short_description = 'Ø§Ù„Ø¨Ù†Ø±Ø§Øª'

    def active_badge(self, obj):
        if obj.is_active:
            return mark_safe('<span class="badge badge-green">Ù…ÙØ¹Ù„</span>')
        return mark_safe('<span class="badge badge-red">Ù…ØªÙˆÙ‚Ù</span>')
    active_badge.short_description = 'Ø§Ù„Ø­Ø§Ù„Ø©'


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
        ('ðŸŽŸï¸ Ø§Ù„ÙƒÙˆØ¯', {
            'fields': ('code', 'sponsor'),
            'description': 'Ø§Ù„ÙƒÙˆØ¯ ÙŠÙÙˆÙ„ÙŽÙ‘Ø¯ ØªÙ„Ù‚Ø§Ø¦ÙŠØ§Ù‹ ÙˆÙ„Ø§ ÙŠÙ…ÙƒÙ† ØªØ¹Ø¯ÙŠÙ„Ù‡ ÙŠØ¯ÙˆÙŠØ§Ù‹.'
        }),
        ('ðŸ”¢ Ø§Ù„Ø­Ø§Ù„Ø©', {
            'fields': ('status',),
        }),
        ('ðŸ“… Ø§Ù„ØªÙˆØ§Ø±ÙŠØ®', {
            'fields': ('created_at', 'used_at'),
        }),
        ('ðŸ‘¤ Ø§Ù„ØªØ­Ù‚Ù‚', {
            'fields': ('verified_by',),
        }),
    )

    def status_badge(self, obj):
        if obj.status == 'used':
            return mark_safe('<span class="badge badge-red">Ù…Ø³ØªØ®Ø¯Ù…</span>')
        return mark_safe('<span class="badge badge-green">Ù†Ø´Ø·</span>')
    status_badge.short_description = 'Ø§Ù„Ø­Ø§Ù„Ø©'

    def verified_by_display(self, obj):
        if obj.verified_by:
            return format_html('<span style="color:#1d4ed8;">{}</span>', obj.verified_by)
        return 'â€”'
    verified_by_display.short_description = 'ØªÙ… Ø§Ù„ØªØ­Ù‚Ù‚ Ù…Ù† Ù‚Ø¨Ù„'


admin.site.site_header = 'Ø³ÙŠØ§Ø±ØªÙŠ Â· Ù„ÙˆØ­Ø© Ø§Ù„Ø¥Ø¯Ø§Ø±Ø©'
admin.site.site_title = 'Ø³ÙŠØ§Ø±ØªÙŠ'
admin.site.index_title = 'Ù„ÙˆØ­Ø© Ø§Ù„ØªØ­ÙƒÙ…'
admin.site.index_template = 'admin/custom_index.html'


DASH_STATS_CACHE_KEY = 'admin_dash_stats'
DASH_STATS_CACHE_TTL = 60


def get_dashboard_stats():
    """Ø¥Ø­ØµØ§Ø¡Ø§Øª Ù„ÙˆØ­Ø© Ø§Ù„ØªØ­ÙƒÙ… â€” ØªÙØ­Ø³Ø¨ ÙˆØªÙØ®Ø²ÙŽÙ‘Ù† Ø¯Ù‚ÙŠÙ‚Ø© ÙƒØ§Ù…Ù„Ø© Ø­ØªÙ‰ Ù„Ø§ ØªÙØ«Ù‚ÙŽÙ„ ÙƒÙ„ ØµÙØ­Ø© Ø¥Ø¯Ø§Ø±Ø©.

    ØªÙÙ…Ø³Ø­ ØªÙ„Ù‚Ø§Ø¦ÙŠØ§Ù‹ Ø¨Ø§Ù†ØªÙ‡Ø§Ø¡ Ø§Ù„ØµÙ„Ø§Ø­ÙŠØ© (60 Ø«Ø§Ù†ÙŠØ©)Ø› Ø§Ù„Ø£Ø±Ù‚Ø§Ù… Ø¯Ø§Ø®Ù„ 60 Ø«Ø§Ù†ÙŠØ© ÙƒØ§ÙÙŠØ© Ù„Ù„ÙˆØ­Ø©.
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
            'verified_by': c.verified_by or 'â€”',
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
