from django.contrib import admin
from .models import Notification, PerformanceAnalytics, SystemAnalytics, AutomatedReport, LearningInsight

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'notification_type', 'title', 'priority', 'is_read', 'created_at']
    list_filter = ['notification_type', 'priority', 'is_read', 'created_at']
    search_fields = ['recipient__username', 'title', 'message']
    readonly_fields = ['created_at', 'sent_at']

@admin.register(PerformanceAnalytics)
class PerformanceAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['student', 'subject', 'current_gpa', 'attendance_percentage', 'risk_level', 'analysis_date']
    list_filter = ['risk_level', 'grade_trend', 'analysis_date']
    search_fields = ['student__user__username', 'student__user__first_name', 'student__user__last_name']

@admin.register(SystemAnalytics)
class SystemAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_students', 'overall_attendance_rate', 'average_gpa', 'students_at_risk']
    list_filter = ['date']
    readonly_fields = ['date']

@admin.register(AutomatedReport)
class AutomatedReportAdmin(admin.ModelAdmin):
    list_display = ['report_type', 'title', 'generated_for', 'generated_at', 'is_automated']
    list_filter = ['report_type', 'is_automated', 'generated_at']
    search_fields = ['title', 'generated_for__username']

@admin.register(LearningInsight)
class LearningInsightAdmin(admin.ModelAdmin):
    list_display = ['student', 'insight_type', 'title', 'confidence_score', 'created_at', 'is_active']
    list_filter = ['insight_type', 'is_active', 'created_at']
    search_fields = ['student__user__username', 'title', 'description']