from django.db import transaction
from django.db.models import Count
from accounts.models import User
from accounts.utils import generate_user_id, generate_random_password
from core.models import House
from .models import Student

class StudentService:
    @staticmethod
    @transaction.atomic
    def enroll_student(data):
        """
        Admits a new student, creates their credentials, 
        and performs automated house assignment.
        """
        # 1. Create User Identity
        username = generate_user_id('student')
        password = generate_random_password(12)
        
        user = User.objects.create_user(
            username=username,
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            password=password,
            role='student'
        )
        
        # 2. Initialize Student Profile
        student, created = Student.objects.get_or_create(user=user)
        student.student_id = username
        
        # 3. Automated House Assignment (Round Robin)
        if not student.house:
            houses = list(House.objects.all().order_by('id'))
            if houses:
                # Optimized count excluding self
                student_count = Student.objects.exclude(pk=student.pk).count()
                next_house_index = student_count % len(houses)
                student.house = houses[next_house_index]
        
        # 4. Populate Attributes
        student.class_enrolled = data.get('class_enrolled')
        student.enrollment_date = data.get('enrollment_date')
        student.age = data.get('age')
        student.gender = data.get('gender', '')
        student.status = data.get('status', 'active')
        student.hobbies = data.get('hobbies', '')
        student.parent_name = data.get('parent_name', '')
        student.parent_phone = data.get('parent_phone', '')
        student.parent_email = data.get('parent_email', '')
        student.parent_relationship = data.get('parent_relationship', '')
        student.emergency_contact_name = data.get('emergency_contact_name', '')
        student.emergency_contact_phone = data.get('emergency_contact_phone', '')
        student.emergency_contact_relationship = data.get('emergency_contact_relationship', '')
        
        student.save()
        
        # Store auto-generated credentials for UI feedback
        student._generated_password = password
        student._generated_username = username
        
        return student

    @staticmethod
    @transaction.atomic
    def update_student(student_instance, user_data, student_data):
        """Updates both user and student records atomically."""
        user = student_instance.user
        
        # Update User fields
        if 'first_name' in user_data:
            user.first_name = user_data['first_name']
        if 'last_name' in user_data:
            user.last_name = user_data['last_name']
        if user_data.get('password'):
            user.set_password(user_data['password'])
        user.save()
        
        # Update Student fields
        for attr, value in student_data.items():
            setattr(student_instance, attr, value)
        student_instance.save()
        
        return student_instance
