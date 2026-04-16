from django.urls import path
from . import views

urlpatterns = [
    path('search/', views.global_search, name='global_search'),
    path('pulse/', views.pulse_diagnostics, name='pulse_diagnostics'),
]