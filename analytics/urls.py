from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('', views.analytics_dashboard, name='analytics_dashboard'),
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/create/', views.create_notification, name='create_notification'),
    path('reports/generate/', views.generate_report, name='generate_report'),
    path('student/<int:student_id>/performance/', views.student_performance_detail, name='student_performance_detail'),
    path('student/<int:student_id>/report-card/', views.generate_report_card, name='generate_report_card'),
    path('student/<int:student_id>/transcript/', views.generate_transcript, name='generate_transcript'),
]