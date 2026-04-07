from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Class, Subject, Attendance, Result, Assignment, Submission
from students.models import Student
from teachers.models import Teacher

User = get_user_model()

class CoreModelsTest(TestCase):
    def setUp(self):
        # Create users
        self.admin_user = User.objects.create_user(
            username='admin', email='admin@test.com', password='pass',
            role='admin', first_name='Admin', last_name='User'
        )
        self.teacher_user = User.objects.create_user(
            username='teacher', email='teacher@test.com', password='pass',
            role='teacher', first_name='Teacher', last_name='User'
        )
        self.teacher_user2 = User.objects.create_user(
            username='teacher2', email='teacher2@test.com', password='pass',
            role='teacher', first_name='Teacher2', last_name='User'
        )
        self.student_user = User.objects.create_user(
            username='student', email='student@test.com', password='pass',
            role='student', first_name='Student', last_name='User'
        )

        # Create related objects
        self.subject = Subject.objects.create(name='Mathematics', code='MATH101')
        self.class_obj = Class.objects.create(
            name='Class 10A', section='A', grade='10', class_teacher=self.teacher_user2
        )

        # Fetch signal-created Student profile (created automatically via signal on user creation)
        self.student = Student.objects.get(user=self.student_user)
        self.student.student_id = 'STU001'
        self.student.class_enrolled = self.class_obj
        self.student.save()

    def test_class_creation(self):
        self.assertEqual(str(self.class_obj), 'Class 10A A')
        self.assertEqual(self.class_obj.grade, '10')

    def test_subject_creation(self):
        self.assertEqual(str(self.subject), 'Mathematics')
        self.assertEqual(self.subject.code, 'MATH101')

    def test_attendance_creation(self):
        attendance = Attendance.objects.create(
            student=self.student, class_attended=self.class_obj,
            date='2024-01-01', status='present', marked_by=self.teacher_user
        )
        self.assertEqual(attendance.status, 'present')

    def test_result_creation(self):
        result = Result.objects.create(
            student=self.student, subject=self.subject, exam_type='midterm',
            score=85.5, max_score=100, teacher=self.teacher_user
        )
        self.assertEqual(str(result), f'{self.student} - {self.subject} - 85.5/100')
        self.assertEqual(result.score, 85.5)

    def test_assignment_creation(self):
        assignment = Assignment.objects.create(
            title='Math Homework', description='Solve problems 1-10',
            subject=self.subject, class_assigned=self.class_obj,
            teacher=self.teacher_user, due_date='2024-01-15'
        )
        self.assertEqual(str(assignment), 'Math Homework')
        self.assertEqual(assignment.due_date, '2024-01-15')

    def test_submission_creation(self):
        assignment = Assignment.objects.create(
            title='Math Homework', description='Solve problems 1-10',
            subject=self.subject, class_assigned=self.class_obj,
            teacher=self.teacher_user, due_date='2024-01-15'
        )
        submission = Submission.objects.create(
            assignment=assignment, student=self.student, grade=90.0, feedback='Good work'
        )
        self.assertEqual(str(submission), f'{self.student} - {assignment}')
        self.assertEqual(submission.grade, 90.0)
