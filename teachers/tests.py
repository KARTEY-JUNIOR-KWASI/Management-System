from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Teacher
from core.models import Subject

User = get_user_model()

class TeacherModelTest(TestCase):
    def setUp(self):
        # Teacher profile is created by signal on User creation
        self.user = User.objects.create_user(
            username='teacher1', email='teacher1@test.com', password='pass',
            role='teacher', first_name='Jane', last_name='Smith'
        )
        self.subject = Subject.objects.create(name='Physics', code='PHY101')

    def test_teacher_creation(self):
        # Fetch the signal-created teacher profile and update it
        teacher = Teacher.objects.get(user=self.user)
        teacher.teacher_id = 'TEA001'
        teacher.qualification = 'masters'
        teacher.save()
        
        teacher.subjects.add(self.subject)
        self.assertEqual(str(teacher), 'Jane Smith')
        self.assertEqual(teacher.teacher_id, 'TEA001')
        self.assertEqual(teacher.qualification, 'masters')
        self.assertIn(self.subject, teacher.subjects.all())
