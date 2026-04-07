from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from .models import Student
from core.models import Class

User = get_user_model()

class StudentModelTest(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='student1', email='student1@test.com', password='pass',
            role='student', first_name='John', last_name='Doe'
        )

    def test_student_creation(self):
        # The profile is automatically created by signals in accounts/signals.py
        student = Student.objects.get(user=self.user)
        student.student_id = 'STU001'
        student.age = 16
        student.save()
        
        self.assertEqual(str(student), 'John Doe')
        self.assertEqual(student.student_id, 'STU001')
        self.assertEqual(student.status, 'active')

    def test_student_without_name(self):
        user_no_name = User.objects.create_user(
            username='student2', email='student2@test.com', password='pass', role='student'
        )
        # Profile exists because of signal
        student = Student.objects.get(user=user_no_name)
        student.student_id = 'STU002'
        student.save()
        
        # Test the fallback __str__
        self.assertEqual(str(student), 'STU002')
