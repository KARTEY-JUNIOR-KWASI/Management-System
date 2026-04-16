from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('attendance/mark/', views.mark_attendance, name='mark_attendance'),
    path('attendance/report/', views.attendance_report, name='attendance_report'),
    path('grades/manage/', views.manage_grades, name='manage_grades'),
    path('grades/report/', views.grade_report, name='grade_report'),
    path('assignments/create/', views.create_assignment, name='create_assignment'),
    path('assignments/manage/', views.manage_assignments, name='manage_assignments'),
    path('assignments/<int:assignment_id>/grade/', views.grade_submissions, name='grade_submissions'),
    path('students/<int:student_id>/report-card/', views.student_report_card, name='student_report_card'),
    path('timetable/', views.teacher_timetable, name='teacher_timetable'),
    path('merit/award/', views.award_merit, name='award_merit'),
]