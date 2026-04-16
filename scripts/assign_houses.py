import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from students.models import Student
from core.models import House

def assign_houses():
    houses = list(House.objects.all().order_by('id'))
    if not houses:
        print("Error: No houses found in the database.")
        return

    students = Student.objects.filter(house__isnull=True).order_by('id')
    print(f"Assigning houses to {students.count()} students...")

    for i, student in enumerate(students):
        house = houses[i % len(houses)]
        student.house = house
        student.save()
        print(f"Assigned {student.user.get_full_name()} to {house.name} House.")

    print("Success: All students have been assigned to houses.")

if __name__ == "__main__":
    assign_houses()
