from django.urls import path
from . import views

urlpatterns = [
    # Teacher
    path('teacher/', views.teacher_library, name='teacher_library'),
    path('teacher/upload/', views.upload_resource, name='upload_resource'),
    path('teacher/edit/<int:pk>/', views.edit_resource, name='edit_resource'),
    path('teacher/delete/<int:pk>/', views.delete_resource, name='delete_resource'),

    # Student
    path('student/', views.student_library, name='student_library'),
    path('student/view/<int:pk>/', views.view_resource, name='view_resource'),
]
