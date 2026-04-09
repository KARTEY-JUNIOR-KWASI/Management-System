import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.contrib.auth import get_user_model
from students.models import Student
from core.models import House, Class

User = get_user_model()

def test_house_assignment():
    print("Testing Centralized House Assignment...")
    
    # Ensure we have houses
    houses = House.objects.all().order_by('id')
    if not houses:
        print("No houses found. Run seeding script first.")
        return
    
    # Ensure we have a class
    class_obj, _ = Class.objects.get_or_create(name="Test Class", defaults={'section': 'A', 'grade': '1'})
    
    # 1. Test via User creation (Signals)
    print("\nMethod 1: Direct User Creation (triggers signal)")
    u1 = User.objects.create_user(username="test_student_signal", password="pass", role='student')
    s1 = Student.objects.get(user=u1)
    print(f"Student: {u1.username} -> Assigned House: {s1.house.name if s1.house else 'None'} ({s1.house.color_code if s1.house else ''})")

    # 2. Test via StudentService (Admin Enrollment)
    print("\nMethod 2: StudentService Enrollment")
    from students.services import StudentService
    data = {
        'first_name': 'Service',
        'last_name': 'Test',
        'class_enrolled': class_obj,
        'enrollment_date': '2024-01-01'
    }
    s2 = StudentService.enroll_student(data)
    print(f"Student: {s2.user.username} -> Assigned House: {s2.house.name if s2.house else 'None'} ({s2.house.color_code if s2.house else ''})")

    # 3. Verify Round Robin
    print("\nVerifying Balanced Distribution (House 3 and 4)...")
    u3 = User.objects.create_user(username="test_student_h3", password="pass", role='student')
    s3 = Student.objects.get(user=u3)
    u4 = User.objects.create_user(username="test_student_h4", password="pass", role='student')
    s4 = Student.objects.get(user=u4)
    
    print(f"Student 3: {s3.house.name if s3.house else 'None'}")
    print(f"Student 4: {s4.house.name if s4.house else 'None'}")

    # Cleanup test data
    # Careful with deletion in a real env, but here it's for verification
    u1.delete()
    s2.user.delete()
    u3.delete()
    u4.delete()
    print("\nVerification Complete.")

if __name__ == "__main__":
    test_house_assignment()
