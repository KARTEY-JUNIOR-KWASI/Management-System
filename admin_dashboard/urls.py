from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_dashboard, name='admin_dashboard'),
    path('students/', views.student_list, name='student_list'),
    path('students/create/', views.student_create, name='student_create'),
    path('students/<int:pk>/update/', views.student_update, name='student_update'),
    path('students/<int:pk>/delete/', views.student_delete, name='student_delete'),
    path('students/<int:pk>/', views.student_detail, name='student_detail'),
    path('teachers/', views.teacher_list, name='teacher_list'),
    path('teachers/create/', views.teacher_create, name='teacher_create'),
    path('teachers/<int:pk>/update/', views.teacher_update, name='teacher_update'),
    path('teachers/<int:pk>/delete/', views.teacher_delete, name='teacher_delete'),
    path('teachers/<int:pk>/', views.teacher_detail, name='teacher_detail'),
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/create/', views.subject_create, name='subject_create'),
    path('subjects/<int:pk>/update/', views.subject_update, name='subject_update'),
    path('subjects/<int:pk>/delete/', views.subject_delete, name='subject_delete'),
    path('classes/', views.class_list, name='class_list'),
    path('classes/create/', views.class_create, name='class_create'),
    path('classes/<int:pk>/update/', views.class_update, name='class_update'),
    path('classes/<int:pk>/delete/', views.class_delete, name='class_delete'),
    
    # Timetable URLs
    path('timetable/manage/', views.manage_timetable, name='manage_timetable'),
    path('timetable/<int:pk>/delete/', views.delete_timetable_entry, name='delete_timetable_entry'),
    
    # Institutional Settings
    path('settings/', views.system_settings, name='system_settings'),
    
    # Academic Intelligence
    path('academic/diagnostics/', views.academic_diagnostics, name='academic_diagnostics'),
    path('academic/class/<int:class_id>/performance/', views.class_performance_analytics, name='class_performance'),

    # Audit & Intelligence
    path('audit/logs/', views.audit_log_list, name='audit_logs'),
    path('notices/create/', views.create_notice, name='create_notice'),
]
