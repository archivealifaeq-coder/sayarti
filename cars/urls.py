from django.urls import path
from . import views

urlpatterns = [
    path('', views.index_view, name='index'),
    path('search/', views.search_view, name='search'),
    path('dealers/', views.dealers_view, name='dealers'),
    path('mix/', views.mix_calculator_view, name='mix_calculator'),
    path('get-suggestions/', views.get_suggestions, name='get_suggestions'),
    path('car/<int:car_id>/recommendations/', views.recommendations_view, name='recommendations'),
    path('privacy/', views.privacy_view, name='privacy'),
    path('about/', views.about_view, name='about'),
    path('ads.txt', views.ads_txt_view, name='ads_txt'),
    path('search/ai-suggest/', views.search_ai_suggest, name='search_ai_suggest'),
    path('search/quick/', views.search_ai_quick, name='search_ai_quick'),
    path('api/stats/app-install/', views.track_app_install, name='track_app_install'),
    path('api/stats/dealer/<int:dealer_id>/<str:action>/', views.track_dealer_click, name='track_dealer_click'),
    path('api/promo-code/generate/', views.generate_promo_code, name='generate_promo_code'),
    path('verify/<slug:slug>/', views.verify_code_page, name='verify_code'),
    path('services/', views.services_login, name='services_login'),
    path('services/dashboard/', views.services_dashboard, name='services_dashboard'),
    path('services/logout/', views.services_logout, name='services_logout'),
]
