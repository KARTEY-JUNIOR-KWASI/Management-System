from django.urls import path
from . import views

urlpatterns = [
    path('', views.profile, name='profile'),
    path('api/onboarding/complete/', views.complete_onboarding, name='complete_onboarding'),
]