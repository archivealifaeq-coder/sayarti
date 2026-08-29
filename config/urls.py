from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve as media_serve
from cars.views import manifest_view, sw_view, robots_view, sitemap_view

urlpatterns = [
    path('robots.txt', robots_view, name='robots_txt'),
    path('sitemap.xml', sitemap_view, name='sitemap'),
    path('admin/', admin.site.urls),
    path('manifest.json', manifest_view, name='manifest'),
    path('sw.js', sw_view, name='service_worker'),
    path('', include('cars.urls')),
]

# Serve uploaded media directly (works even when DEBUG=False; WhiteNoise handles /static/)
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', media_serve, {'document_root': settings.MEDIA_ROOT}),
]
