from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve as media_serve
from cars.views import manifest_view, sw_view, robots_view, sitemap_view, admin_codes_report
import os

# مسار لوحة الإدارة قابل للتحويل من .env (مثال ADMIN_URL=cpanel/)
# لتقليل التعرض للهجمات الآلية على المسار الافتراضي
_ADMIN_PATH = os.getenv('ADMIN_URL', 'admin/').strip().strip('/') + '/'
# مسار بلا شرطة زائدة للبناء المشترك
_ADMIN_BASE = _ADMIN_PATH.strip('/')

urlpatterns = [
    path('robots.txt', robots_view, name='robots_txt'),
    path('sitemap.xml', sitemap_view, name='sitemap'),
    # تقرير أكواد الخصم — يُسجَّل قبل لوحة الإدارة حتى لا يبتلعه مسار الادمن
    path(f'{_ADMIN_BASE}/report/codes/', admin_codes_report, name='admin_codes_report'),
    path(_ADMIN_PATH, admin.site.urls),
    path('manifest.json', manifest_view, name='manifest'),
    path('sw.js', sw_view, name='service_worker'),
    path('', include('cars.urls')),
]

# Serve uploaded media directly (works even when DEBUG=False; WhiteNoise handles /static/)
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', media_serve, {'document_root': settings.MEDIA_ROOT}),
]
