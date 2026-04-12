import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()
from admin_dashboard.forms import StudentForm
from core.models import Class
from students.models import Student
import random

# Use a dynamic student ID to avoid unique constraint errors
student_id = f'STD{random.randint(10000, 99999)}'
cls = Class.objects.first()

if not cls:
    print("Error: No Class found in database. Please seed the database first.")
else:
    data = {
        'student_id': student_id,
        'first_name': 'Test',
        'last_name': 'Student',
        'password': 'password123',
        'class_enrolled': cls.id,
        'enrollment_date': '2026-04-07',
        'age': 15,
        'gender': 'male',
        'status': 'active'
    }
    
    print(f"--- Testing Student Creation with ID: {student_id} ---")
    form = StudentForm(data)
    if form.is_valid():
        try:
            student = form.save()
            print(f'SUCCESS: Student {student.student_id} saved.')
        except Exception as e:
            print(f'DATABASE ERROR: {e}')
    else:
        print(f'FORM ERRORS: {form.errors}')

