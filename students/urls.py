from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.student_dashboard, name='student_dashboard'),
    path('grades/', views.view_grades, name='view_grades'),
    path('attendance/', views.view_attendance, name='view_attendance'),
    path('assignments/', views.view_assignments, name='view_assignments'),
    path('assignments/<int:assignment_id>/submit/', views.submit_assignment, name='submit_assignment'),
    path('timetable/', views.student_timetable, name='student_timetable'),
    path('house-alliance/', views.house_alliance_hub, name='house_alliance_hub'),
    path('report-pdf/', views.download_report_card_pdf, name='download_report_card_pdf'),
    path('guardian/dashboard/', views.guardian_dashboard, name='guardian_dashboard'),
    path('guardian/ward/<int:student_id>/', views.guardian_ward_detail, name='guardian_ward_detail'),
]