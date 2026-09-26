from django.urls import path
from . import views

urlpatterns = [
    path('', views.front, name='front'),
    path('home/', views.home, name='home'),
    path('analysis/', views.analysis_page, name='analysis'),
    path('about/', views.about, name='about'),
    path('map/', views.map_view, name='map'),
]
