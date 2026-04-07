from django.db import models

class Class(models.Model):
    name = models.CharField(max_length=100)
    section = models.CharField(max_length=10, blank=True)
    grade = models.CharField(max_length=10)
    class_teacher = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name='class_teacher')

    class Meta:
        indexes = [
            models.Index(fields=['grade']),
        ]

    def __str__(self):
        return f"{self.name} {self.section}"

class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Attendance(models.Model):
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='attendances')
    class_attended = models.ForeignKey('Class', on_delete=models.CASCADE)
    date = models.DateField()
    status = models.CharField(max_length=10, choices=[('present', 'Present'), ('absent', 'Absent'), ('late', 'Late')])
    marked_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['student', 'date', 'class_attended'], name='unique_attendance')
        ]
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['status']),
            models.Index(fields=['student', 'date']),
        ]

    def __str__(self):
        return f"{self.student} - {self.date} - {self.status}"

class Result(models.Model):
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='results')
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    exam_type = models.CharField(max_length=20, choices=[('midterm', 'Midterm'), ('final', 'Final'), ('quiz', 'Quiz')])
    score = models.DecimalField(max_digits=5, decimal_places=2)
    max_score = models.DecimalField(max_digits=5, decimal_places=2)
    date = models.DateField(auto_now_add=True)
    teacher = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['student', 'subject']),
            models.Index(fields=['date']),
            models.Index(fields=['exam_type']),
        ]

    def __str__(self):
        return f"{self.student} - {self.subject} - {self.score}/{self.max_score}"

class Assignment(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    class_assigned = models.ForeignKey('Class', on_delete=models.CASCADE, related_name='assignments')
    teacher = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    due_date = models.DateField()
    file = models.FileField(upload_to='assignments/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['due_date']),
            models.Index(fields=['class_assigned']),
            models.Index(fields=['teacher']),
        ]

    def __str__(self):
        return self.title

class Submission(models.Model):
    assignment = models.ForeignKey('Assignment', on_delete=models.CASCADE)
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='submissions')
    file = models.FileField(upload_to='submissions/', null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['assignment', 'student'], name='unique_submission')
        ]
        indexes = [
            models.Index(fields=['assignment', 'student']),
            models.Index(fields=['submitted_at']),
        ]

    def __str__(self):
        return f"{self.student} - {self.assignment}"

class Notification(models.Model):
    title = models.CharField(max_length=200)
    message = models.TextField()
    sender = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    recipients = models.ManyToManyField('accounts.User', related_name='core_notifications')
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return self.title

class Timetable(models.Model):
    DAYS = [
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
    ]
    class_assigned = models.ForeignKey('Class', on_delete=models.CASCADE)
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    teacher = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    day = models.CharField(max_length=10, choices=DAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['class_assigned', 'day', 'start_time'], name='unique_timetable')
        ]
        indexes = [
            models.Index(fields=['day', 'start_time']),
            models.Index(fields=['teacher', 'day']),
        ]

    def __str__(self):
        return f"{self.class_assigned} - {self.day} - {self.subject}"
