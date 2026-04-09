from django.db import models
from django.conf import settings
from django.utils import timezone

class House(models.Model):
    """Institutional house system for student identification and competition."""
    name = models.CharField(max_length=100, unique=True)
    color_code = models.CharField(max_length=20, default="#4361ee", help_text="Hex color code for identification (e.g. #FF0000)")
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Institutional House"
        verbose_name_plural = "Institutional Houses"

    def __str__(self):
        return self.name

class AcademicTerm(models.Model):
    """Naming and duration for institutional periods (e.g. First Term 2024)."""
    name = models.CharField(max_length=100)
    session = models.CharField(max_length=20, help_text="e.g. 2024/2025")
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_date']
        verbose_name = "Academic Term"
        verbose_name_plural = "Academic Terms"

    def __str__(self):
        return f"{self.name} ({self.session})"

    def save(self, *args, **kwargs):
        if self.is_current:
            # Ensure only one term is 'current'
            AcademicTerm.objects.filter(is_current=True).update(is_current=False)
        super().save(*args, **kwargs)

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


class SchoolConfiguration(models.Model):
    """Singleton model for overall institutional configuration."""
    name = models.CharField(max_length=200, default="Edu Ms Intelligence")
    motto = models.CharField(max_length=300, blank=True, default="Empowering Future Leaders")
    logo = models.ImageField(upload_to='school/', null=True, blank=True)
    contact_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    current_academic_year = models.CharField(max_length=20, default="2025-2026")
    established_year = models.IntegerField(default=2024)
    active_term = models.ForeignKey(AcademicTerm, on_delete=models.SET_NULL, null=True, blank=True)
    
    # 🌍 Financial Localization Node
    currency_symbol = models.CharField(max_length=10, default="GH₵")
    currency_code = models.CharField(max_length=10, default="GHS")
    
    class Meta:
        verbose_name = "Institutional Configuration"
        verbose_name_plural = "Institutional Configuration"

    def __str__(self):
        return self.name

    @classmethod
    def get_config(cls):
        """Helper to get the singleton instance."""
        obj, created = cls.objects.get_or_create(id=1)
        return obj

class AuditLog(models.Model):
    """System-wide tracking for institutional activity and security."""
    ACTION_CHOICES = [
        ('LOGIN', 'User Login'),
        ('LOGOUT', 'User Logout'),
        ('CREATE', 'Record Created'),
        ('UPDATE', 'Record Updated'),
        ('DELETE', 'Record Deleted'),
        ('SYSTEM', 'System Configuration Change'),
        ('SECURITY', 'Security Alert'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=100, help_text="e.g. Student, Result, Teacher")
    resource_id = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['resource_type', 'resource_id']),
        ]

    def __str__(self):
        return f"{self.user} - {self.action} - {self.resource_type} ({self.timestamp})"
class NoticeBoard(models.Model):
    """Institutional announcements and global notices."""
    CATEGORY_CHOICES = [
        ('academic', 'Academic'),
        ('sports', 'Sports'),
        ('event', 'Event'),
        ('emergency', 'Emergency'),
        ('general', 'General Announcement'),
    ]

    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        verbose_name = "Institutional Notice"
        verbose_name_plural = "Institutional Notices"

    def __str__(self):
        return f"{self.get_category_display()}: {self.title}"
