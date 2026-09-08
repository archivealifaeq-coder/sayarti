from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from cars.views import manifest_view, sw_view, robots_view, sitemap_view, admin_codes_report, admin_cars_report
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
    path(f'{_ADMIN_BASE}/report/cars/', admin_cars_report, name='admin_cars_report'),
    path(_ADMIN_PATH, admin.site.urls),
    path('manifest.json', manifest_view, name='manifest'),
    path('sw.js', sw_view, name='service_worker'),
    path('', include('cars.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
