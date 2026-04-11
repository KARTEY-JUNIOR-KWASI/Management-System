import os
import django
from django.test import Client
from django.urls import reverse

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from accounts.models import User
from students.models import Student
from teachers.models import Teacher

def run_dashboard_tests():
    c = Client()
    
    print("\n--- ANALYTICS STABILIZATION VERIFICATION ---\n")
    
    # 1. Test Student Dashboard
    student_user = User.objects.filter(role='student').first()
    if student_user:
        print(f"Testing Student Dashboard for: {student_user.username}")
        c.force_login(student_user)
        try:
            response = c.get(reverse('student_dashboard'))
            print(f"Student Dashboard Status: {response.status_code}")
            if response.status_code != 200:
                print(f"ERROR: Student Dashboard failed with status {response.status_code}")
        except Exception as e:
            print(f"CRITICAL ERROR (Student Dashboard): {e}")
    else:
        print("Skipping Student Dashboard: No student user found.")

    # 2. Test Teacher Dashboard
    teacher_user = User.objects.filter(role='teacher').first()
    if teacher_user:
        print(f"\nTesting Teacher Dashboard for: {teacher_user.username}")
        c.force_login(teacher_user)
        try:
            # Test Core Dashboard
            response = c.get(reverse('teacher_dashboard'))
            print(f"Teacher Core Dashboard Status: {response.status_code}")
            
            # Test Analytics Dashboard
            response = c.get(reverse('analytics:analytics_dashboard'))
            print(f"Teacher Analytics Dashboard Status: {response.status_code}")
        except Exception as e:
            print(f"CRITICAL ERROR (Teacher Dashboard): {e}")
    else:
        print("Skipping Teacher Dashboard: No teacher user found.")

    # 3. Test Admin Analytics Dashboard
    admin_user = User.objects.filter(role='admin').first()
    if admin_user:
        print(f"\nTesting Admin Analytics Dashboard for: {admin_user.username}")
        c.force_login(admin_user)
        try:
            response = c.get(reverse('analytics:analytics_dashboard'))
            print(f"Admin Analytics Dashboard Status: {response.status_code}")
        except Exception as e:
            print(f"CRITICAL ERROR (Admin Dashboard): {e}")
    else:
        print("Skipping Admin Analytics: No admin user found.")

    print("\n--- VERIFICATION COMPLETE ---\n")

if __name__ == "__main__":
    run_dashboard_tests()
