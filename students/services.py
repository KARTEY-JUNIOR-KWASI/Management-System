from django.db import transaction
from django.db.models import Count
from accounts.models import User
from accounts.utils import generate_user_id, generate_random_password
from core.models import House
from .models import Student, Guardian

class StudentService:
    @staticmethod
    def _sync_guardian_link(student, parent_email):
        """
        Internal utility to synchronize the link between a Student and their Guardian profile
        based on the provided parent email. Handles automatic account creation for new guardians.
        """
        if not parent_email:
            student.guardian = None
            student.save()
            return None

        # Check if a guardian with this email already exists
        parent_user = User.objects.filter(email=parent_email, role='parent').first()
        
        if not parent_user:
            # Create a new Guardian Identity
            p_username = generate_user_id('parent')
            p_password = generate_random_password(12)
            
            parent_user = User.objects.create_user(
                username=p_username,
                email=parent_email,
                first_name=student.parent_name or 'Guardian',
                password=p_password,
                role='parent'
            )
            
            guardian_profile = Guardian.objects.create(
                user=parent_user,
                phone=student.parent_phone or '',
                relationship_to_student=student.parent_relationship or ''
            )
            
            # Internal markers for UI feedback during creation
            student._parent_generated_username = p_username
            student._parent_generated_password = p_password
        else:
            guardian_profile = getattr(parent_user, 'guardian_profile', None)
            if not guardian_profile:
                guardian_profile = Guardian.objects.create(user=parent_user)

        # Secure the link
        student.guardian = guardian_profile
        student.save()
        return guardian_profile

    @staticmethod
    def assign_automated_house(student):
        """
        Performs Round Robin house assignment for a student.
        Ensures balanced distribution across institutional houses.
        """
        if not student.house:
            houses = list(House.objects.all().order_by('id'))
            if houses:
                student_count = Student.objects.exclude(pk=student.pk).count()
                next_house_index = student_count % len(houses)
                student.house = houses[next_house_index]
                student.save()
                return student.house
        return student.house

    @staticmethod
    def sync_all_unassigned_students():
        """
        Repair Tool: Identifies and aligns all students who are currently 
        orphaned from the Institutional House system.
        """
        unassigned = Student.objects.filter(house__isnull=True)
        count = unassigned.count()
        for student in unassigned:
            StudentService.assign_automated_house(student)
        return count

    @staticmethod
    @transaction.atomic
    def enroll_student(data):
        """
        Admits a new student, creates their credentials, 
        and performs automated house/guardian synchronization.
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
        student, created = Student.objects.get_or_create(
            user=user,
            defaults={'student_id': username}
        )
        if not student.student_id:
            student.student_id = username
        
        # 3. Automated Protocol Assets
        StudentService.assign_automated_house(student)
        
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
        
        # 5. Guardian Hub Activation
        StudentService._sync_guardian_link(student, data.get('parent_email'))
        
        # 6. Success Metadata Injection
        student._generated_password = password
        student._generated_username = username
        
        return student

    @staticmethod
    @transaction.atomic
    def update_student(student_instance, user_data, student_data):
        """Updates both user and student records atomically, including guardian re-sync."""
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
        
        # Synchronize Guardian link if email changed
        if 'parent_email' in student_data:
            StudentService._sync_guardian_link(student_instance, student_data['parent_email'])
        else:
            student_instance.save()
        
        return student_instance
