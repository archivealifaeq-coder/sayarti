from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve as media_serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('cars.urls')),
]

# ✅ خدمة صور البنرات (media) تعمل حتى لو DEBUG=False
# الملفات الثابتة (static) تخدمها WhiteNoise من settings.py
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', media_serve, {'document_root': settings.MEDIA_ROOT}),
]
