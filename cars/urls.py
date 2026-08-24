from django.urls import path
from . import views

urlpatterns = [
    path('', views.index_view, name='index'),
    path('import/', views.import_excel_view, name='import_excel'),
    path('mix/', views.mix_calculator_view, name='mix_calculator'),
    path('get-suggestions/', views.get_suggestions, name='get_suggestions'),
    path('car/<int:car_id>/recommendations/', views.recommendations_view, name='recommendations'),
]
