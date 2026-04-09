from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from students.models import Student
from teachers.models import Teacher
from core.models import Class, Subject, Attendance

User = get_user_model()

class AdminDashboardTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username='admin', email='admin@test.com', password='pass',
            role='admin', first_name='Admin', last_name='User'
        )
        self.teacher_user = User.objects.create_user(
            username='teacher', email='teacher@test.com', password='pass',
            role='teacher', first_name='Teacher', last_name='User'
        )
        self.student_user = User.objects.create_user(
            username='student', email='student@test.com', password='pass',
            role='student', first_name='Student', last_name='User'
        )

        # Create test data
        self.subject = Subject.objects.create(name='Test Subject', code='TS101')
        self.class_obj = Class.objects.create(
            name='Test Class', section='A', grade='10', class_teacher=self.teacher_user
        )

        # Fetch signal-created Student profile and set it up
        self.student = Student.objects.get(user=self.student_user)
        self.student.student_id = 'STU001'
        self.student.class_enrolled = self.class_obj
        self.student.save()

        # Fetch signal-created Teacher profile and set it up
        self.teacher = Teacher.objects.get(user=self.teacher_user)
        self.teacher.teacher_id = 'TEA001'
        self.teacher.save()

        # Create attendance records
        Attendance.objects.create(
            student=self.student, class_attended=self.class_obj,
            date='2024-01-01', status='present', marked_by=self.admin_user
        )
        Attendance.objects.create(
            student=self.student, class_attended=self.class_obj,
            date='2024-01-02', status='absent', marked_by=self.admin_user
        )

    def test_admin_dashboard_view(self):
        """Dashboard should load with 200 and contain key UI elements."""
        self.client.login(username='admin', password='pass')
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        # Check that the context carries the expected values
        self.assertIn('total_students', response.context)
        self.assertIn('total_teachers', response.context)
        self.assertEqual(response.context['total_students'], 1)

    def test_student_list_view(self):
        """Student list should be accessible and show the student's ID."""
        self.client.login(username='admin', password='pass')
        response = self.client.get(reverse('student_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'STU001')

    def test_unauthorized_access(self):
        """Non-admin users should be redirected away from admin views."""
        self.client.login(username='student', password='pass')
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 403)  # Forbidden for non-admin students
