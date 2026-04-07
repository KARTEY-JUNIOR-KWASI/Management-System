from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/<int:pk>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/read-all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('dashboard/', views.home, name='dashboard'),  # Fallback for NoReverseMatch
]