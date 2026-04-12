from django.db import transaction
from accounts.models import User
from accounts.utils import generate_user_id, generate_random_password
from .models import Teacher

class TeacherService:
    @staticmethod
    @transaction.atomic
    def onboard_teacher(user_data, teacher_data, subject_ids=None):
        """
        Onboards a new faculty member, creates credentials, 
        and initializes their professional profile.
        """
        # 1. Create User Identity
        username = generate_user_id('teacher')
        password = generate_random_password(12)
        
        user = User.objects.create_user(
            username=username,
            email=user_data.get('email'),
            first_name=user_data.get('first_name'),
            last_name=user_data.get('last_name'),
            password=password,
            role='teacher',
            gender=user_data.get('gender', ''),
            phone=user_data.get('phone', ''),
            address=user_data.get('address', ''),
            date_of_birth=user_data.get('date_of_birth')
        )
        
        if user_data.get('profile_picture'):
            user.profile_picture = user_data['profile_picture']
        user.save()
        
        # 2. Initialize Teacher Profile
        teacher, created = Teacher.objects.get_or_create(
            user=user,
            defaults={'teacher_id': username}
        )
        
        # Ensure ID is correct if profile already existed without one (legacy safety)
        if not teacher.teacher_id:
            teacher.teacher_id = username
            
        teacher.department = teacher_data.get('department', '')
        teacher.qualification = teacher_data.get('qualification', '')
        teacher.specialization = teacher_data.get('specialization', '')
        teacher.emergency_contact_name = teacher_data.get('emergency_contact_name', '')
        teacher.emergency_contact_phone = teacher_data.get('emergency_contact_phone', '')
        teacher.emergency_contact_relationship = teacher_data.get('emergency_contact_relationship', '')
        teacher.save()
        
        if subject_ids:
            teacher.subjects.set(subject_ids)
            
        # Store metadata for feedback
        teacher._generated_password = password
        teacher._generated_username = username
        
        return teacher

    @staticmethod
    @transaction.atomic
    def update_teacher(teacher_instance, user_data, teacher_data, subject_ids=None):
        """Updates teacher and user records atomically."""
        user = teacher_instance.user
        
        # Update User core identity
        for attr in ['first_name', 'last_name', 'email', 'gender', 'phone', 'address', 'date_of_birth']:
            if attr in user_data:
                setattr(user, attr, user_data[attr])
        
        if user_data.get('profile_picture'):
            user.profile_picture = user_data['profile_picture']
        
        if user_data.get('password'):
            user.set_password(user_data['password'])
        user.save()
        
        # Update Teacher profile
        for attr, value in teacher_data.items():
            setattr(teacher_instance, attr, value)
        teacher_instance.save()
        
        if subject_ids is not None:
            teacher_instance.subjects.set(subject_ids)
            
        return teacher_instance
