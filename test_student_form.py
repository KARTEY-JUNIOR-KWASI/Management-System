import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()
from admin_dashboard.forms import StudentForm
from core.models import Class
cls = Class.objects.first()
data = {'student_id': 'STD12399', 'first_name': 'Test', 'last_name': 'Student', 'password': 'password123', 'class_enrolled': cls.id, 'enrollment_date': '2026-04-07', 'age': 15, 'gender': 'male', 'status': 'active'}
form = StudentForm(data)
if form.is_valid():
    form.save()
    print('Saved')
else:
    print(form.errors)
