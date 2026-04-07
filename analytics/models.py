from django.db import models
from django.contrib.auth import get_user_model
from students.models import Student
from core.models import Subject, Class
from datetime import datetime, timedelta

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('assignment', 'Assignment'),
        ('grade', 'Grade'),
        ('attendance', 'Attendance'),
        ('announcement', 'Announcement'),
        ('reminder', 'Reminder'),
    ]

    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    recipient = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='analytics_notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='medium')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    # Related objects (optional)
    related_student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True)
    related_subject = models.ForeignKey(Subject, on_delete=models.CASCADE, null=True, blank=True)
    related_class = models.ForeignKey(Class, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.notification_type}: {self.title} - {self.recipient.username}"

class PerformanceAnalytics(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    analysis_date = models.DateField(auto_now_add=True)

    # Performance metrics
    current_gpa = models.FloatField()
    attendance_percentage = models.FloatField()
    assignment_completion_rate = models.FloatField()
    grade_trend = models.CharField(max_length=20)  # 'improving', 'declining', 'stable'

    # Predictions
    predicted_final_grade = models.FloatField(null=True, blank=True)
    risk_level = models.CharField(max_length=20)  # 'low', 'medium', 'high', 'critical'

    # Insights
    strengths = models.TextField(blank=True)
    areas_for_improvement = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)

    class Meta:
        unique_together = ['student', 'subject', 'analysis_date']
        ordering = ['-analysis_date']

class SystemAnalytics(models.Model):
    date = models.DateField(unique=True)
    total_students = models.IntegerField()
    total_teachers = models.IntegerField()
    total_classes = models.IntegerField()
    total_subjects = models.IntegerField()

    # Attendance stats
    overall_attendance_rate = models.FloatField()
    attendance_trend = models.CharField(max_length=20)  # 'improving', 'declining', 'stable'

    # Academic stats
    average_gpa = models.FloatField()
    assignment_completion_rate = models.FloatField()

    # Risk indicators
    students_at_risk = models.IntegerField()  # Students with low attendance/grades
    critical_cases = models.IntegerField()  # Students needing immediate attention

    class Meta:
        ordering = ['-date']

class AutomatedReport(models.Model):
    REPORT_TYPES = [
        ('progress', 'Progress Report'),
        ('attendance', 'Attendance Report'),
        ('performance', 'Performance Analysis'),
        ('summary', 'Monthly Summary'),
    ]

    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    title = models.CharField(max_length=200)
    generated_for = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True)
    class_group = models.ForeignKey(Class, on_delete=models.CASCADE, null=True, blank=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, null=True, blank=True)

    # Date range
    start_date = models.DateField()
    end_date = models.DateField()

    # Report content
    content = models.JSONField()  # Store structured report data
    pdf_file = models.FileField(upload_to='reports/', null=True, blank=True)

    # Metadata
    generated_at = models.DateTimeField(auto_now_add=True)
    is_automated = models.BooleanField(default=True)

    class Meta:
        ordering = ['-generated_at']

class LearningInsight(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    insight_type = models.CharField(max_length=50)  # 'attendance_pattern', 'grade_trend', 'learning_style', etc.
    title = models.CharField(max_length=200)
    description = models.TextField()
    confidence_score = models.FloatField()  # 0-1, how confident the system is in this insight
    data_points = models.JSONField()  # Supporting data
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']