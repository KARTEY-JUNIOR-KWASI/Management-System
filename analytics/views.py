from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Count, Q, F
from django.db.models.functions import TruncMonth
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.views.decorators.cache import cache_page
from django.utils import timezone
from datetime import datetime, timedelta, date
import json
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

from .models import Notification, PerformanceAnalytics, SystemAnalytics, AutomatedReport, LearningInsight
from students.models import Student
from teachers.models import Teacher
from core.models import Subject, Class, Result, Attendance, Assignment, Submission
from accounts.models import User
from .analytics_engine import _calculate_student_performance, _generate_grade_predictions
from .reporting_utils import (
    calculate_letter_grade, get_student_class_rank, get_institutional_metadata, 
    draw_institutional_seal, draw_performance_chart
)


def _redirect_wrong_role(request, role):
    messages.error(request, f'You must be logged in as a {role} to access that page.')
    return redirect('home')



def _get_or_create_student(user):
    from students.models import Student
    student, created = Student.objects.get_or_create(
        user=user,
        defaults={
            'student_id': f'STUD{user.id:05d}',
        }
    )
    return student


def _get_or_create_teacher(user):
    teacher, created = Teacher.objects.get_or_create(
        user=user,
        defaults={
            'teacher_id': f'TCHR{user.id:05d}',
        }
    )
    return teacher

@login_required
def analytics_dashboard(request):
    """Smart analytics dashboard with insights and predictions"""
    user = request.user

    if user.role == 'admin':
        return admin_analytics_dashboard(request)
    elif user.role == 'teacher':
        return teacher_analytics_dashboard(request)
    else:
        return student_analytics_dashboard(request)

@login_required
@cache_page(60 * 15)  # Cache for 15 minutes
def admin_analytics_dashboard(request):
    """Admin dashboard with system-wide analytics"""
    if request.user.role != 'admin':
        messages.error(request, 'Access Denied: Administrative privileges required.')
        return redirect('home')
    
    # Generate system analytics if not exists for today
    today = date.today()
    analytics_data = _calculate_system_analytics()
    # Ensure only valid model fields are passed to get_or_create
    valid_fields = {f.name for f in SystemAnalytics._meta.get_fields()}
    safe_defaults = {k: v for k, v in analytics_data.items() if k in valid_fields}

    system_analytics, created = SystemAnalytics.objects.get_or_create(
        date=today,
        defaults=safe_defaults
    )

    # Get recent notifications
    recent_notifications = Notification.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=7)
    ).order_by('-created_at')[:10]

    # Get performance trends
    performance_trend = _calculate_performance_trend()

    # Risk analysis
    at_risk_students = _identify_at_risk_students()

    context = {
        'system_analytics': system_analytics,
        'recent_notifications': recent_notifications,
        'performance_trend': performance_trend,
        'at_risk_students': at_risk_students[:10],  # Top 10 at-risk students
        'total_at_risk': len(at_risk_students),
    }
    return render(request, 'analytics/admin_dashboard.html', context)

@login_required
def teacher_analytics_dashboard(request):
    """Teacher dashboard with class and student analytics"""
    if request.user.role != 'teacher':
        return _redirect_wrong_role(request, 'teacher')

    teacher = _get_or_create_teacher(request.user)

    # Class performance overview
    class_performance = _calculate_class_performance(teacher)

    # Student insights
    student_insights = _generate_student_insights(teacher)

    # Assignment analytics
    assignment_stats = _calculate_assignment_stats(teacher)

    # Recent notifications
    recent_notifications = list(Notification.objects.filter(
        recipient=request.user,
        created_at__gte=timezone.now() - timedelta(days=7)
    ).order_by('-created_at')[:5])

    context = {
        'class_performance': class_performance,
        'student_insights': student_insights,
        'assignment_stats': assignment_stats,
        'recent_notifications': recent_notifications,
    }
    return render(request, 'analytics/teacher_dashboard.html', context)

@login_required
def student_analytics_dashboard(request):
    """Student dashboard with personal analytics and predictions"""
    if request.user.role != 'student':
        return _redirect_wrong_role(request, 'student')

    student = _get_or_create_student(request.user)

    # Personal performance analytics
    performance_data = _calculate_student_performance(student)

    # Learning insights
    insights = list(LearningInsight.objects.filter(
        student=student,
        is_active=True
    ).order_by('-confidence_score')[:5])

    # Grade predictions
    predictions = list(_generate_grade_predictions(student))

    # Recent notifications
    recent_notifications = list(Notification.objects.filter(
        recipient=request.user,
        created_at__gte=timezone.now() - timedelta(days=7)
    ).order_by('-created_at')[:5])

    context = {
        'performance_data': performance_data,
        'insights': insights,
        'predictions': predictions,
        'recent_notifications': recent_notifications,
    }
    return render(request, 'analytics/student_dashboard.html', context)

@login_required
def create_notification(request):
    """Create and send notifications"""
    if request.method == 'POST':
        notification_type = request.POST.get('notification_type')
        title = request.POST.get('title')
        message = request.POST.get('message')
        priority = request.POST.get('priority', 'medium')
        recipients = request.POST.getlist('recipients')

        # Bulk optimization: Fetch all recipients in one query and use bulk_create
        recipients_qs = User.objects.filter(id__in=recipients)
        
        notification_objs = [
            Notification(
                recipient=recipient,
                notification_type=notification_type,
                title=title,
                message=message,
                priority=priority
            ) for recipient in recipients_qs
        ]
        
        Notification.objects.bulk_create(notification_objs)

        # Send email notifications if configured
        _send_email_notifications(title, message, recipients)

        messages.success(request, f'Notification sent to {len(notification_objs)} recipients!')
        return redirect('analytics:analytics_dashboard')

    # Get potential recipients based on user role
    user = request.user
    if user.role == 'admin':
        recipients = User.objects.all()
    elif user.role == 'teacher':
        teacher = _get_or_create_teacher(request.user)
        # Get students in teacher's classes
        class_ids = Class.objects.filter(class_teacher=request.user).values_list('id', flat=True)
        recipients = User.objects.filter(
            Q(role='student', student__class_enrolled__id__in=class_ids) |
            Q(role='admin')
        )
    else:
        recipients = User.objects.filter(role='admin')

    context = {
        'recipients': recipients,
    }
    return render(request, 'analytics/create_notification.html', context)

@login_required
def generate_report(request):
    """Generate automated reports"""
    if request.method == 'POST':
        report_type = request.POST.get('report_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        if report_type == 'progress':
            return _generate_progress_report(request, start_date, end_date)
        elif report_type == 'attendance':
            return _generate_attendance_report(request, start_date, end_date)
        elif report_type == 'performance':
            return _generate_performance_report(request, start_date, end_date)

    context = {
        'today': date.today(),
        'last_month': date.today() - timedelta(days=30),
    }
    return render(request, 'analytics/generate_report.html', context)

@login_required
def notifications_list(request):
    """View and manage notifications"""
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')

    # Mark unread notifications as read
    unread_count = notifications.filter(is_read=False).count()
    urgent_count = notifications.filter(priority='urgent').count()
    low_priority_count = notifications.filter(priority='low').count()
    notifications.filter(is_read=False).update(is_read=True)

    context = {
        'notifications': notifications,
        'unread_count': unread_count,
        'urgent_count': urgent_count,
        'low_priority_count': low_priority_count,
    }
    return render(request, 'analytics/notifications.html', context)

@login_required
def student_performance_detail(request, student_id):
    """Detailed performance analysis for a specific student"""
    student = get_object_or_404(Student, id=student_id)

    # Check permissions
    user = request.user
    if user.role == 'student' and student.user != request.user:
        messages.error(request, 'You can only view your own performance.')
        return redirect('analytics_dashboard')

    performance_data = _calculate_student_performance(student)
    insights = LearningInsight.objects.filter(student=student, is_active=True)
    predictions = _generate_grade_predictions(student)

    context = {
        'student': student,
        'performance_data': performance_data,
        'insights': insights,
        'predictions': predictions,
    }
    return render(request, 'analytics/student_performance_detail.html', context)

# Helper functions for analytics calculations

def _calculate_system_analytics():
    """
    Calculate system-wide analytics.
    Optimized with bulk aggregation for high-speed reporting.
    """
    # Bulk aggregate core counts
    core_counts = {
        'total_students': Student.objects.count(),
        'total_teachers': Teacher.objects.count(),
        'total_classes': Class.objects.count(),
        'total_subjects': Subject.objects.count(),
    }

    # Attendance rate in one query
    att_stats = Attendance.objects.aggregate(
        total=Count('id'),
        present=Count('id', filter=Q(status='present'))
    )
    overall_attendance_rate = (att_stats['present'] / att_stats['total'] * 100) if att_stats['total'] > 0 else 0

    # Average GPA in one query
    avg_score = Result.objects.aggregate(avg=Avg('score'))['avg'] or 0
    average_gpa = min(4.0, avg_score / 25)

    # Assignment completion rate
    # Optimizing by using direct counts
    assignment_count = Assignment.objects.count()
    if assignment_count > 0:
        submission_count = Submission.objects.count()
        # Note: This is a system-wide average across all assignments
        assignment_completion_rate = (submission_count / (assignment_count * core_counts['total_students'])) * 100 if core_counts['total_students'] > 0 else 0
    else:
        assignment_completion_rate = 0

    # Students at risk (Use the existing optimized helper)
    at_risk_students = _identify_at_risk_students()
    
    # Attendance trend
    attendance_trend = _calculate_attendance_trend()
    
    return {
        **core_counts,
        'overall_attendance_rate': overall_attendance_rate,
        'attendance_trend': attendance_trend,
        'average_gpa': average_gpa,
        'assignment_completion_rate': assignment_completion_rate,
        'students_at_risk': len(at_risk_students),
        'critical_cases': len([s for s in at_risk_students if s['risk_level'] == 'critical']),
    }

def _calculate_performance_trend():
    """
    Calculate performance trends over time.
    Performance: Refactored from 6 queries to 1 using TruncMonth and Avg.
    """
    # Get last 6 months of data
    six_months_ago = date.today() - timedelta(days=180)
    
    trends = Result.objects.filter(
        date__gte=six_months_ago
    ).annotate(
        month=TruncMonth('date')
    ).values('month').annotate(
        avg_score=Avg('score')
    ).order_by('month')

    return [
        {
            'month': (t['month'] if isinstance(t['month'], (date, datetime)) else datetime.strptime(t['month'], '%Y-%m-%d')).strftime('%b %Y') if t['month'] else "Unknown",
            'average_score': float(t['avg_score'] or 0),
        }
        for t in trends
    ]

def _identify_at_risk_students():
    """
    Identify students who need attention.
    Performance: Refactored from O(N) to O(1) database hit by using bulk annotations.
    """
    thirty_days_ago = date.today() - timedelta(days=30)
    
    # Bulk annotate all students with performance stats and recent assignment counts
    # This replaces the previous logic that did 3+ queries per student
    students = Student.objects.with_performance_stats().annotate(
        recent_assignment_count=Count(
            'class_enrolled__assignments',
            filter=Q(class_enrolled__assignments__due_date__gte=thirty_days_ago),
            distinct=True
        ),
        recent_submission_count=Count(
            'submissions',
            filter=Q(submissions__assignment__due_date__gte=thirty_days_ago),
            distinct=True
        )
    ).select_related('user', 'class_enrolled')

    at_risk_students = []

    for student in students:
        # Use annotated values from with_performance_stats()
        attendance_rate = student.annotated_attendance_rate
        gpa = student.annotated_gpa

        risk_score = 0
        risk_factors = []

        if attendance_rate < 75:
            risk_score += 2
            risk_factors.append('Low attendance')
        elif attendance_rate < 85:
            risk_score += 1
            risk_factors.append('Below average attendance')

        if gpa < 2.0:
            risk_score += 3
            risk_factors.append('Low GPA')
        elif gpa < 2.5:
            risk_score += 1
            risk_factors.append('Below average GPA')

        # Check recent assignment completion using annotated counts
        if student.recent_assignment_count > 0:
            completion_rate = (student.recent_submission_count / student.recent_assignment_count) * 100
            if completion_rate < 50:
                risk_score += 2
                risk_factors.append('Low assignment completion')

        # Determine risk level
        if risk_score >= 4:
            risk_level = 'critical'
        elif risk_score >= 2:
            risk_level = 'high'
        elif risk_score >= 1:
            risk_level = 'medium'
        else:
            continue  # No risk

        if risk_level in ['high', 'critical']:
            at_risk_students.append({
                'student': student,
                'risk_level': risk_level,
                'risk_score': risk_score,
                'risk_factors': risk_factors,
                'attendance_rate': attendance_rate,
                'gpa': gpa,
            })

    return sorted(at_risk_students, key=lambda x: x['risk_score'], reverse=True)


def _calculate_subject_heatmap(teacher):
    """
    Generate a 2D performance matrix for heatmap visualization.
    Maps [Subject] x [Class] -> Average Percentage.
    """
    from core.models import Result, Class
    from django.db.models import Avg, F, ExpressionWrapper, FloatField
    
    # Get relevant entities
    subjects = teacher.subjects.all()
    # We need teacher classes from teachers.views, or we can re-derive them here
    # For now, let's get any class that has results for these subjects taught by this teacher
    teacher_classes = Class.objects.filter(
        student__results__teacher=teacher.user,
        student__results__subject__in=subjects
    ).distinct()

    if not teacher_classes.exists():
        # Fallback: get classes assigned to the teacher
        from teachers.views import _get_teacher_classes
        teacher_classes = _get_teacher_classes(teacher.user)

    heatmap_data = {
        'subjects': [s.name for s in subjects],
        'classes': [c.name for c in teacher_classes],
        'matrix': []
    }

    for subject in subjects:
        row = []
        for class_obj in teacher_classes:
            results_in_context = Result.objects.filter(
                subject=subject,
                student__class_enrolled=class_obj,
                teacher=teacher.user
            )
            
            if results_in_context.exists():
                # Correct way to aggregate an expression in modern Django
                # Or use a simpler approach if ratio is causing visibility issues
                stats = results_in_context.annotate(
                    item_ratio=ExpressionWrapper(F('score') * 100.0 / F('max_score'), output_field=FloatField())
                ).aggregate(avg_ratio=Avg('item_ratio'))
                normalized_avg = stats['avg_ratio'] or 0
            else:
                normalized_avg = 0

            row.append(float(normalized_avg))
        heatmap_data['matrix'].append(row)

    return heatmap_data

def _calculate_class_performance(teacher):
    """
    Calculate performance metrics for teacher's classes.
    Optimized with prefetch_related and bulk aggregation.
    """
    classes_data = []
    # Use select_related to get class details in one query
    teacher_classes = Class.objects.filter(class_teacher=teacher.user).prefetch_related('student_set')

    for class_obj in teacher_classes:
        students_in_class = class_obj.student_set.all()
        student_count = students_in_class.count()

        if student_count == 0:
            classes_data.append({
                'class': class_obj,
                'student_count': 0,
                'avg_gpa': 0,
                'attendance_rate': 0,
                'completion_rate': 0,
            })
            continue

        avg_score = float(Result.objects.filter(student__in=students_in_class).aggregate(avg=Avg('score'))['avg'] or 0)
        avg_gpa = min(4.0, (avg_score / 25))

        # Attendance rate in one aggregate query
        attendance_stats = Attendance.objects.filter(
            student__in=students_in_class,
            class_attended=class_obj
        ).aggregate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present'))
        )
        total_att = attendance_stats['total']
        attendance_rate = (attendance_stats['present'] / total_att * 100) if total_att > 0 else 0

        # Assignment completion
        assignments = Assignment.objects.filter(teacher=teacher.user, class_assigned=class_obj)
        assignment_count = assignments.count()
        
        if assignment_count > 0:
            submission_count = Submission.objects.filter(assignment__in=assignments).count()
            completion_rate = (submission_count / (assignment_count * student_count)) * 100
        else:
            completion_rate = 0

        classes_data.append({
            'class': class_obj,
            'student_count': student_count,
            'avg_gpa': avg_gpa,
            'attendance_rate': attendance_rate,
            'completion_rate': completion_rate,
        })

    return classes_data

def _generate_student_insights(teacher):
    """Generate insights about students for teachers"""
    insights = []
    teacher_classes = Class.objects.filter(class_teacher=teacher.user)

    for class_obj in teacher_classes:
        students = Student.objects.filter(class_enrolled=class_obj)

        for student in students:
            recent_results = list(Result.objects.filter(student=student).order_by('-date')[:3])
            if len(recent_results) >= 2:
                scores = [r.score for r in recent_results]
                if scores[0] < scores[-1] - 10:  # Declining by more than 10 points
                    insights.append({
                        'student': student,
                        'type': 'performance_decline',
                        'message': f'{student.user.get_full_name()} shows declining performance',
                        'severity': 'high',
                    })

            recent_attendance = list(Attendance.objects.filter(
                student=student,
                class_attended=class_obj
            ).order_by('-date')[:5])

            absent_count = len([r for r in recent_attendance if r.status == 'absent'])
            if absent_count >= 3:
                insights.append({
                    'student': student,
                    'type': 'attendance_concern',
                    'message': f'{student.user.get_full_name()} has been absent {absent_count} times recently',
                    'severity': 'medium',
                })

    return list(insights[:10])  # Return top 10 insights as a list

def _calculate_assignment_stats(teacher):
    """Calculate assignment statistics for teacher"""
    assignments = Assignment.objects.filter(teacher=teacher.user)
    total_assignments = assignments.count()

    if total_assignments == 0:
        return {
            'total_assignments': 0,
            'total_submissions': 0,
            'completion_rate': 0,
            'avg_grade': 0,
        }

    submissions = Submission.objects.filter(assignment__in=assignments)
    total_submissions = submissions.count()

    # Calculate completion rate
    expected_submissions = total_assignments * Student.objects.filter(
        class_enrolled__in=assignments.values_list('class_assigned', flat=True).distinct()
    ).count()

    completion_rate = (total_submissions / expected_submissions * 100) if expected_submissions > 0 else 0

    # Average grade
    graded_submissions = submissions.filter(grade__isnull=False)
    avg_grade = graded_submissions.aggregate(avg=Avg('grade'))['avg'] or 0

    return {
        'total_assignments': total_assignments,
        'total_submissions': total_submissions,
        'completion_rate': completion_rate,
        'avg_grade': avg_grade,
    }

    # Note: Analytics calculations are now handled by analytics_engine.py

def _calculate_attendance_trend():
    """Calculate attendance trend over the last two months"""
    today = date.today()
    last_month_end = today.replace(day=1) - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    prev_month_end = last_month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)

    # Current month attendance
    current_month_attendance = Attendance.objects.filter(date__range=(last_month_start, last_month_end))
    if current_month_attendance.exists():
        current_rate = (current_month_attendance.filter(status='present').count() / current_month_attendance.count()) * 100
    else:
        current_rate = 0

    # Previous month attendance
    prev_month_attendance = Attendance.objects.filter(date__range=(prev_month_start, prev_month_end))
    if prev_month_attendance.exists():
        prev_rate = (prev_month_attendance.filter(status='present').count() / prev_month_attendance.count()) * 100
    else:
        prev_rate = 0

    if current_rate > prev_rate + 5:
        return 'improving'
    elif current_rate < prev_rate - 5:
        return 'declining'
    else:
        return 'stable'

def _send_email_notifications(title, message, recipient_ids):
    """Send email notifications"""
    try:
        recipients = User.objects.filter(id__in=recipient_ids)
        recipient_emails = [user.email for user in recipients if user.email]

        if recipient_emails:
            send_mail(
                subject=f'School Management System: {title}',
                message=strip_tags(message),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_emails,
                html_message=message,
                fail_silently=True,
            )
    except Exception as e:
        # Log error but don't break the flow
        print(f"Email sending failed: {e}")

def _generate_progress_report(request, start_date, end_date):
    """Generate student progress report - clean institutional PDF matching the EduMS design."""
    from django.contrib import messages
    from django.shortcuts import redirect
    
    if request.user.role != 'student':
        return _redirect_wrong_role(request, 'student')

    student = _get_or_create_student(request.user)
    
    # 🔒 Institutional Finance Guard: Block PDF generation if student has unpaid fees
    from finance.models import Invoice
    has_unpaid = Invoice.objects.filter(student=student, status__in=['unpaid', 'partial']).exists()
    if has_unpaid:
        messages.error(request, 'SECURITY LOCK: Academic Report Cards are restricted until outstanding fees are cleared.')
        return redirect('finance:student_finance_hub')
        
    config = get_institutional_metadata()

    # Fetch ALL student results (not date-limited so card is always useful)
    results = Result.objects.filter(student=student).select_related('subject').order_by('subject__name', 'exam_type')

    # Attendance
    all_attendance = Attendance.objects.filter(student=student)
    att_total   = all_attendance.count()
    att_present = all_attendance.filter(status='present').count()
    att_pct     = round((att_present / att_total * 100), 1) if att_total > 0 else 0.0

    # Build subject results
    subject_results = {}
    for r in results:
        sn = r.subject.name
        if sn not in subject_results:
            subject_results[sn] = {'rows': [], 'avg': 0}
        pct = round((r.score / r.max_score * 100), 1) if r.max_score else 0.0
        if pct >= 80:   gl = 'A'
        elif pct >= 70: gl = 'B'
        elif pct >= 60: gl = 'C'
        elif pct >= 50: gl = 'D'
        else:           gl = 'F'
        subject_results[sn]['rows'].append({
            'exam_type': r.get_exam_type_display() if hasattr(r, 'get_exam_type_display') else r.exam_type,
            'score': r.score,
            'max_score': r.max_score,
            'percentage': pct,
            'grade': gl,
        })

    for sn, data in subject_results.items():
        if data['rows']:
            data['avg'] = round(sum(x['percentage'] for x in data['rows']) / len(data['rows']), 1)

    all_pcts = [x['percentage'] for d in subject_results.values() for x in d['rows']]
    overall_avg = round(sum(all_pcts) / len(all_pcts), 1) if all_pcts else 0.0

    if overall_avg >= 80:   overall_grade = 'A'
    elif overall_avg >= 70: overall_grade = 'B'
    elif overall_avg >= 60: overall_grade = 'C'
    elif overall_avg >= 50: overall_grade = 'D'
    else:                   overall_grade = 'F'

    # Compute Ranking / Position calculations
    subject_ranks = {}
    overall_class_position = None
    total_class_students = 0

    if student.class_enrolled:
        from django.db.models import Sum
        class_results = Result.objects.filter(student__class_enrolled=student.class_enrolled)
        
        # 1. Overall Position
        overall_scores = list(
            class_results.values('student_id').annotate(total_score=Sum('score')).order_by('-total_score')
        )
        total_class_students = len(overall_scores)
        for i, res in enumerate(overall_scores):
            if res['student_id'] == student.id:
                overall_class_position = i + 1
                break
                
        # 2. Subject Position
        # We need to rank for each subject the student took.
        subj_scores = list(
            class_results.values('student_id', 'subject__name').annotate(total_score=Sum('score')).order_by('subject__name', '-total_score')
        )
        
        # Group subj_scores by subject
        from itertools import groupby
        from operator import itemgetter
        
        for subj, group in groupby(subj_scores, key=itemgetter('subject__name')):
            group_list = list(group)
            for i, res in enumerate(group_list):
                if res['student_id'] == student.id:
                    subject_ranks[subj] = {
                        'pos': i + 1,
                        'total_students': len(group_list)
                    }
                    break

    # Intelligent remarks based on actual performance
    if not results.exists():
        remark = ("This student has not yet submitted any assessments for the current academic period. "
                  "Early engagement with academic work is strongly encouraged to build a solid foundation for success.")
    elif overall_avg >= 90:
        remark = ("Outstanding performance! This student has demonstrated exceptional mastery across all subjects. "
                  "Their dedication and hard work are truly commendable. We encourage maintaining this excellent standard.")
    elif overall_avg >= 75:
        remark = ("Very good performance. This student is performing well above the class average. "
                  "With continued effort and focus, achieving top distinction is well within reach.")
    elif overall_avg >= 60:
        remark = ("Good performance overall. The student shows a satisfactory understanding of core subjects. "
                  "Targeted revision in lower-scoring areas will help push results to a higher tier.")
    elif overall_avg >= 50:
        remark = ("Average performance. The student requires more consistent effort and preparation to improve results. "
                  "We recommend seeking additional academic support and dedicating more time to studies.")
    else:
        remark = ("This student's performance is below the expected standard. Immediate attention and dedicated study are "
                  "required. We strongly encourage working closely with class teachers to address areas of weakness.")

    # ── Build PDF ──────────────────────────────────────────────────────────────
    PRIMARY   = colors.HexColor('#1e3a5f')
    ACCENT    = colors.HexColor('#2563eb')
    SUCCESS   = colors.HexColor('#10b981')
    WARNING   = colors.HexColor('#f59e0b')
    DANGER    = colors.HexColor('#ef4444')
    MUTED     = colors.HexColor('#64748b')
    BORDER    = colors.HexColor('#e2e8f0')
    BG        = colors.HexColor('#f8fafc')
    WHITE     = colors.white

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )

    # Style helpers (inline — no global registration to avoid KeyError)
    def _s(size, bold=False, color=None, align=0, italic=False):
        return ParagraphStyle(
            name=f'_tmp_{size}_{bold}_{align}',
            fontSize=size,
            fontName=('Helvetica-BoldOblique' if bold and italic else
                      'Helvetica-Bold' if bold else
                      'Helvetica-Oblique' if italic else 'Helvetica'),
            alignment=align,
            textColor=color or colors.black,
            leading=size * 1.3,
        )

    story = []
    W = 539  # usable width

    # ── 1. HEADER BANNER ────────────────────────────────────────────────────────
    school_name  = config.name if config and config.name else 'EduMS'
    acad_year    = config.current_academic_year if config and config.current_academic_year else '2025 / 2026'

    hdr_left  = [
        [Paragraph(f'<b><font color="#2563eb">{school_name[:3]}</font>{school_name[3:]}</b>',
                   _s(22, bold=False, color=WHITE))],
        [Paragraph('School Management System — Official Report Card',
                   _s(8, color=colors.HexColor('#aab4c4')))],
    ]
    hdr_right = [
        [Paragraph('Academic Year', _s(7, color=colors.HexColor('#aab4c4')))],
        [Paragraph(f'<b>{acad_year}</b>', _s(14, bold=True, color=WHITE))],
    ]

    hdr_left_t  = Table(hdr_left,  colWidths=[W * 0.65])
    hdr_right_t = Table(hdr_right, colWidths=[W * 0.35])
    hdr_right_t.setStyle(TableStyle([
        ('BACKGROUND', (0,1),(0,1), colors.HexColor('#2a4a75')),
        ('ROUNDEDCORNERS', [6]*4),
        ('ALIGN', (0,0),(-1,-1), 'RIGHT'),
        ('TOPPADDING',(0,1),(0,1),6), ('BOTTOMPADDING',(0,1),(0,1),6),
        ('LEFTPADDING',(0,1),(0,1),10), ('RIGHTPADDING',(0,1),(0,1),10),
    ]))

    hdr_table = Table([[hdr_left_t, hdr_right_t]], colWidths=[W * 0.65, W * 0.35])
    hdr_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(-1,-1), PRIMARY),
        ('TOPPADDING',   (0,0),(-1,-1), 18),
        ('BOTTOMPADDING',(0,0),(-1,-1), 18),
        ('LEFTPADDING',  (0,0),(-1,-1), 20),
        ('RIGHTPADDING', (0,0),(-1,-1), 20),
        ('VALIGN', (0,0),(-1,-1), 'MIDDLE'),
    ]))
    story.append(hdr_table)

    # ── 2. STUDENT INFO GRID ─────────────────────────────────────────────────────
    teacher_name = ('N/A')
    if student.class_enrolled and student.class_enrolled.class_teacher:
        teacher_name = student.class_enrolled.class_teacher.get_full_name()

    enrollment = student.date_enrolled.strftime('%B %d, %Y') if hasattr(student, 'date_enrolled') and student.date_enrolled else 'N/A'

    def bio_cell(label, value):
        return [
            Paragraph(label, _s(6, bold=True, color=MUTED)),
            Spacer(1, 3),
            Paragraph(f'<b>{value}</b>', _s(9, bold=True, color=PRIMARY)),
        ]

    bio_row1 = [bio_cell('STUDENT NAME', student.user.get_full_name().upper()),
                bio_cell('STUDENT ID',   student.student_id),
                bio_cell('CLASS',        student.class_enrolled.name.upper() if student.class_enrolled else 'N/A')]
    bio_row2 = [bio_cell('ENROLLMENT DATE', enrollment),
                bio_cell('CLASS TEACHER',   teacher_name.upper()),
                bio_cell('GENERATED ON',    datetime.now().strftime('%d %b %Y'))]

    bio1 = Table([bio_row1], colWidths=[W/3, W/3, W/3])
    bio2 = Table([bio_row2], colWidths=[W/3, W/3, W/3])

    for bt in [bio1, bio2]:
        bt.setStyle(TableStyle([
            ('VALIGN',  (0,0),(-1,-1), 'TOP'),
            ('LEFTPADDING',  (0,0),(-1,-1), 16),
            ('RIGHTPADDING', (0,0),(-1,-1), 16),
            ('TOPPADDING',   (0,0),(-1,-1), 12),
            ('BOTTOMPADDING',(0,0),(-1,-1), 12),
            ('LINEAFTER', (0,0),(1,-1), 0.5, BORDER),
            ('LINEBELOW', (0,0),(-1,-1), 0.5, BORDER),
        ]))

    story.append(bio1)
    story.append(bio2)
    story.append(Spacer(1, 10))

    # ── 3. SUMMARY CARDS ─────────────────────────────────────────────────────────
    def summary_card(label, big_val, sub, top_color):
        card = Table([
            [Paragraph(label, _s(6, bold=True, color=MUTED))],
            [Paragraph(f'<b>{big_val}</b>', _s(22, bold=True, color=PRIMARY))],
            [Paragraph(sub, _s(7, color=MUTED))],
        ], colWidths=[(W/3) - 12])
        card.setStyle(TableStyle([
            ('TOPPADDING',   (0,0),(-1,-1), 10),
            ('BOTTOMPADDING',(0,0),(-1,-1), 10),
            ('LEFTPADDING',  (0,0),(-1,-1), 14),
            ('RIGHTPADDING', (0,0),(-1,-1), 14),
            ('LINEABOVE', (0,0),(-1,0), 3, top_color),
            ('BOX', (0,0),(-1,-1), 0.5, BORDER),
            ('ROUNDEDCORNERS', [6]*4),
        ]))
        return card

    card_grade = summary_card('OVERALL GRADE',   overall_grade, f'{overall_avg}% Average', PRIMARY)
    card_avg   = summary_card('OVERALL AVERAGE', f'{overall_avg}%', 'Across all subjects', WARNING)
    card_att   = summary_card('ATTENDANCE',      f'{att_pct}%', f'{att_present} / {att_total} days', SUCCESS)
    
    pos_str = f'{overall_class_position}/{total_class_students}' if overall_class_position else 'N/A'
    card_pos   = summary_card('CLASS POSITION',  pos_str, 'Overall rank in class', ACCENT)

    cards_table = Table([[card_pos, card_grade, card_avg, card_att]],
                        colWidths=[(W/4)-4, (W/4)-4, (W/4)-4, (W/4)-4],
                        hAlign='LEFT')
    cards_table.setStyle(TableStyle([
        ('ALIGN',  (0,0),(-1,-1), 'CENTER'),
        ('VALIGN', (0,0),(-1,-1), 'TOP'),
        ('LEFTPADDING',  (0,0),(-1,-1), 4),
        ('RIGHTPADDING', (0,0),(-1,-1), 4),
    ]))
    story.append(cards_table)
    story.append(Spacer(1, 14))

    # ── 4. ACADEMIC RESULTS TABLE ───────────────────────────────────────────────
    story.append(Paragraph('📚  ACADEMIC RESULTS', _s(8, bold=True, color=PRIMARY)))
    story.append(Spacer(1, 6))

    if subject_results:
        tbl_data = [[
            Paragraph('<b>Subject</b>',   _s(8, bold=True, color=WHITE)),
            Paragraph('<b>Exam Type</b>', _s(8, bold=True, color=WHITE)),
            Paragraph('<b>Score</b>',     _s(8, bold=True, color=WHITE)),
            Paragraph('<b>Max Score</b>', _s(8, bold=True, color=WHITE)),
            Paragraph('<b>Percentage</b>',_s(8, bold=True, color=WHITE)),
            Paragraph('<b>Grade</b>',     _s(8, bold=True, color=WHITE)),
        ]]
        row_styles = [
            ('BACKGROUND', (0,0),(-1,0), PRIMARY),
            ('ALIGN', (0,0),(-1,-1), 'CENTER'),
            ('VALIGN', (0,0),(-1,-1), 'MIDDLE'),
            ('FONTSIZE', (0,0),(-1,-1), 8),
            ('TOPPADDING',   (0,0),(-1,-1), 8),
            ('BOTTOMPADDING',(0,0),(-1,-1), 8),
            ('GRID', (0,0),(-1,-1), 0.4, BORDER),
            ('ROWBACKGROUNDS', (0,1),(-1,-1), [WHITE, BG]),
        ]

        for sn, data in subject_results.items():
            first = True
            for row in data['rows']:
                subj_cell = Paragraph(f'<b>{sn.upper()}</b>', _s(8, bold=True, color=PRIMARY)) if first else Paragraph('', _s(8))
                tbl_data.append([
                    subj_cell,
                    Paragraph(str(row['exam_type']).capitalize(), _s(8)),
                    Paragraph(str(row['score']), _s(8, bold=True, color=PRIMARY)),
                    Paragraph(str(row['max_score']), _s(8, color=MUTED)),
                    Paragraph(f'{row["percentage"]}%', _s(8, bold=True, color=SUCCESS if row["percentage"]>=70 else (WARNING if row["percentage"]>=50 else DANGER))),
                    Paragraph(f'<b>{row["grade"]}</b>', _s(9, bold=True, color=SUCCESS if row["grade"]=="A" else (ACCENT if row["grade"]=="B" else (WARNING if row["grade"] in ("C","D") else DANGER)))),
                ])
                first = False
            # Subject average row with Subject Position
            spos_data = subject_ranks.get(sn, {})
            spos_str = f"Pos: {spos_data.get('pos', 'N/A')}/{spos_data.get('total_students', 'N/A')}" if spos_data else ""
            tbl_data.append([
                Paragraph('', _s(7)),
                Paragraph('', _s(7)),
                Paragraph('', _s(7)),
                Paragraph(f'<b>{spos_str}</b>', _s(7, color=ACCENT)),
                Paragraph(f'{sn.upper()} Average', _s(7, color=MUTED)),
                Paragraph(f'<b>{data["avg"]}%</b>', _s(8, bold=True, color=PRIMARY)),
            ])
            row_styles.append(('BACKGROUND', (0, len(tbl_data)-1), (-1, len(tbl_data)-1), colors.HexColor('#eef2ff')))

        results_table = Table(tbl_data, colWidths=[130, 75, 55, 65, 120, 60])
        results_table.setStyle(TableStyle(row_styles))
        story.append(results_table)
    else:
        story.append(Paragraph('No academic results recorded for this student yet.', _s(9, italic=True, color=MUTED)))

    story.append(Spacer(1, 14))

    # ── 5. TEACHER REMARKS ───────────────────────────────────────────────────────
    story.append(Paragraph('💬  TEACHER REMARKS', _s(8, bold=True, color=PRIMARY)))
    story.append(Spacer(1, 6))

    remarks_inner = Table(
        [[Paragraph(remark, _s(9, italic=True, color=MUTED))]],
        colWidths=[W]
    )
    remarks_inner.setStyle(TableStyle([
        ('BACKGROUND', (0,0),(-1,-1), BG),
        ('BOX', (0,0),(-1,-1), 0.5, BORDER),
        ('TOPPADDING',   (0,0),(-1,-1), 12),
        ('BOTTOMPADDING',(0,0),(-1,-1), 12),
        ('LEFTPADDING',  (0,0),(-1,-1), 14),
        ('RIGHTPADDING', (0,0),(-1,-1), 14),
    ]))
    story.append(remarks_inner)
    story.append(Spacer(1, 20))

    # ── 6. SIGNATURES ────────────────────────────────────────────────────────────
    sig_line = '_' * 42
    sig_data = [
        [Paragraph(sig_line, _s(9, color=BORDER)), Paragraph(sig_line, _s(9, color=BORDER))],
        [Paragraph('Class Teacher', _s(7, bold=True, color=MUTED)),
         Paragraph('Principal / Head of School', _s(7, bold=True, color=MUTED))],
        [Paragraph(f'<b>{teacher_name.upper()}</b>', _s(8, bold=True, color=PRIMARY)),
         Paragraph('', _s(8))],
    ]
    sig_table = Table(sig_data, colWidths=[W/2 - 10, W/2 - 10])
    sig_table.setStyle(TableStyle([
        ('ALIGN',  (0,0),(-1,-1), 'CENTER'),
        ('VALIGN', (0,0),(-1,-1), 'TOP'),
        ('TOPPADDING',   (0,0),(-1,-1), 4),
        ('BOTTOMPADDING',(0,0),(-1,-1), 4),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 6))

    # Footer
    footer_style = _s(7, color=MUTED)
    footer_data = [[
        Paragraph(request.build_absolute_uri('/students/report-pdf/'), footer_style),
        Paragraph(f'{datetime.now().strftime("%d/%m/%Y, %I:%M %p")}', _s(7, color=MUTED, align=2)),
    ]]
    footer_table = Table(footer_data, colWidths=[W * 0.6, W * 0.4])
    story.append(footer_table)

    # Build
    doc.build(story)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="EduMS_Report_{student.student_id}.pdf"'
    return response



def _generate_attendance_report(request, start_date, end_date):
    """Generate attendance report"""
    user = request.user

    if user.role == 'student':
        student = _get_or_create_student(request.user)
        attendance = Attendance.objects.filter(
            student=student,
            date__range=(start_date, end_date)
        ).order_by('date')
        title = f"Attendance Report - {student.user.get_full_name()}"
    else:
        # For teachers and admins, show class attendance
        attendance = Attendance.objects.filter(
            date__range=(start_date, end_date)
        ).select_related('student', 'class_attended').order_by('date', 'student__user__last_name')
        title = f"Class Attendance Report - {start_date} to {end_date}"

    # Generate Premium PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    # Custom Premium Styles
    styles.add(ParagraphStyle(name='PremiumTitle', fontSize=24, fontName='Helvetica-Bold', alignment=1, spaceAfter=2, textColor=colors.HexColor('#0F172A')))
    styles.add(ParagraphStyle(name='PremiumSub', fontSize=10, fontName='Helvetica-Bold', alignment=1, spaceAfter=20, textColor=colors.HexColor('#64748B')))
    styles.add(ParagraphStyle(name='SectionHead', fontSize=14, fontName='Helvetica-Bold', spaceBefore=20, spaceAfter=10, textColor=colors.HexColor('#1E293B'), borderPadding=5, leftIndent=0))
    styles.add(ParagraphStyle(name='MetricLabel', fontSize=9, fontName='Helvetica-Bold', textColor=colors.HexColor('#10B981')))
    styles.add(ParagraphStyle(name='MetricVal', fontSize=18, fontName='Helvetica-Bold', textColor=colors.HexColor('#0F172A')))

    story = []

    # 1. Institutional Header
    config = get_institutional_metadata()
    story.append(Paragraph(config.name.upper(), styles['PremiumTitle']))
    story.append(Paragraph("OFFICIAL ATTENDANCE & PRESENCE PROTOCOL", styles['PremiumSub']))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#10B981'), spaceAfter=20))

    # 2. Scope Matrix
    scope_text = "CLASS-WIDE AUDIT" if request.user.role != 'student' else "INDIVIDUAL PRESENCE"
    id_data = [
        [Paragraph("PROTOCOL SCOPE", styles['MetricLabel']), Paragraph("AUDIT WINDOW", styles['MetricLabel'])],
        [Paragraph(scope_text, styles['MetricVal']), Paragraph(f"{start_date} → {end_date}", styles['MetricVal'])]
    ]
    id_table = Table(id_data, colWidths=[240, 240])
    id_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 10)]))
    story.append(id_table)
    story.append(Spacer(1, 20))

    # 3. Attendance Matrix
    story.append(Paragraph("I. PRESENCE LOGS", styles['SectionHead']))
    if attendance.exists():
        data = [['DATE', 'STUDENT ENTITY', 'SECTOR', 'STATUS']]
        for record in attendance:
            student_name = record.student.user.get_full_name() if hasattr(record, 'student') else "N/A"
            class_name = record.class_attended.name if hasattr(record, 'class_attended') else "N/A"
            data.append([
                record.date.strftime('%Y-%m-%d'),
                student_name.upper(),
                class_name.upper(),
                record.status.title().upper()
            ])

        table = Table(data, colWidths=[100, 180, 100, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("No presence signals detected during this temporal window.", styles['Normal']))

    # 4. Certification Footer
    story.append(Spacer(1, 60))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1')))
    story.append(Spacer(1, 10))
    
    footer_data = [
        [draw_institutional_seal(), "CERTIFIED PRESENCE LOG GENERATED VIA NEXUS PROTOCOL"],
        ["", f"TIMESTAMP: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"]
    ]
    footer_table = Table(footer_data, colWidths=[100, 380])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,1), (-1,1), 7),
        ('TEXTCOLOR', (0,1), (-1,1), colors.grey)
    ]))
    story.append(footer_table)

    # Build PDF
    doc.build(story)
    buffer.seek(0)

    # Create response
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    filename = f"nexus_attendance_{start_date}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def generate_report_card(request, student_id):
    """
    Gold Standard Report Card Generation.
    Features: Branding, Grading, and Class Ranking.
    """
    student = get_object_or_404(Student, id=student_id)
    config = get_institutional_metadata()
    
    # Check permissions (Security)
    if request.user.role == 'student' and student.user != request.user:
        messages.error(request, 'Access denied: unauthorized report request.')
        return redirect('home')

    # Data Aggregation
    results = Result.objects.filter(student=student).select_related('subject')
    performance = []
    total_percentage = 0
    
    for r in results:
        pct = (float(r.score) / float(r.max_score) * 100) if r.max_score > 0 else 0
        grade = calculate_letter_grade(pct)
        performance.append({
            'subject': r.subject.name,
            'score': f"{r.score}/{r.max_score}",
            'percentage': f"{pct:.1f}%",
            'grade': grade
        })
        total_percentage += pct
        
    avg_pct = (total_percentage / results.count()) if results.count() > 0 else 0
    rank, total_peers = get_student_class_rank(student)

    # ──────────────────────────────────────────────────────────
    # [PDF Generation Engine 2.0]
    # ──────────────────────────────────────────────────────────
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    # Custom Styles
    styles.add(ParagraphStyle(name='InstitutionalTitle', fontSize=22, fontName='Helvetica-Bold', alignment=1, spaceAfter=2))
    styles.add(ParagraphStyle(name='SubTitle', fontSize=10, fontName='Helvetica-Bold', alignment=1, textColor=colors.grey))
    styles.add(ParagraphStyle(name='StudentInfo', fontSize=9, fontName='Helvetica', leading=12))
    styles.add(ParagraphStyle(name='SectionHeader', fontSize=12, fontName='Helvetica-Bold', spaceBefore=20, borderPadding=10, backColor=colors.HexColor('#F8FAFC')))
    styles.add(ParagraphStyle(name='RemarkHead', fontSize=10, fontName='Helvetica-Bold', spaceBefore=15, spaceAfter=5, textColor=colors.HexColor('#0F172A')))
    styles.add(ParagraphStyle(name='RemarkBox', fontSize=10, fontName='Helvetica-Oblique', leading=14, borderPadding=12, backColor=colors.HexColor('#F8FAFC'), textColor=colors.HexColor('#475569')))

    story = []

    # 1. Institutional Header
    story.append(Paragraph(config.name.upper(), styles['InstitutionalTitle']))
    story.append(Paragraph(config.motto.upper() or "EMPOWERING FUTURE LEADERS", styles['SubTitle']))
    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=1, lineCap='round', color=colors.HexColor('#E2E8F0')))
    story.append(Spacer(1, 15))

    # 2. Student Identity Matrix
    s_data = [
        [Paragraph(f"<b>STUDENT:</b> {student.user.get_full_name()}", styles['StudentInfo']), 
         Paragraph(f"<b>CLASS:</b> {student.class_enrolled.name if student.class_enrolled else 'N/A'}", styles['StudentInfo'])],
        [Paragraph(f"<b>STUDENT ID:</b> {student.student_id}", styles['StudentInfo']), 
         Paragraph(f"<b>ACADEMIC YEAR:</b> {config.current_academic_year}", styles['StudentInfo'])],
        [Paragraph(f"<b>RANK:</b> {rank} of {total_peers}" if rank else "B: N/A", styles['StudentInfo']), 
         Paragraph(f"<b>AVERAGE:</b> {avg_pct:.1f}%", styles['StudentInfo'])]
    ]
    s_table = Table(s_data, colWidths=[240, 240])
    s_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'LEFT'), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story.append(s_table)
    story.append(Spacer(1, 25))

    # 3. Performance Visualization
    story.append(Paragraph("PERFORMANCE VISUALIZATION", styles['SectionHeader']))
    story.append(Spacer(1, 10))
    story.append(draw_performance_chart(performance))
    story.append(Spacer(1, 20))

    # 4. Academic Achievement Table
    story.append(Paragraph("ACADEMIC PERFORMANCE SUMMARY", styles['SectionHeader']))
    story.append(Spacer(1, 10))
    
    table_data = [['SUBJECT', 'RAW SCORE', 'PERCENTAGE', 'GRADE']]
    for p in performance:
        table_data.append([p['subject'], p['score'], p['percentage'], p['grade']])

    a_table = Table(table_data, colWidths=[180, 100, 100, 100])
    a_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    story.append(a_table)

    # 4. Teacher Remarks
    story.append(Paragraph("TEACHER REMARKS", styles['RemarkHead']))
    remark_text = "Good performance. Continue working hard to achieve excellence."
    story.append(Paragraph(remark_text, styles['RemarkBox']))
    
    story.append(Spacer(1, 40))

    # 5. Dual Signature Protocol (Class Teacher & Principal)
    teacher_name = student.class_enrolled.class_teacher.get_full_name() if student.class_enrolled and student.class_enrolled.class_teacher else "NOT ASSIGNED"
    
    sig_line = "........................................................"
    f_data = [
        [Paragraph(sig_line, styles['Normal']), Paragraph(sig_line, styles['Normal'])],
        [f"Class Teacher: {teacher_name}", "Principal / Head of School"]
    ]
    f_table = Table(f_data, colWidths=[240, 240])
    f_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, 1), 5),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#475569'))
    ]))
    story.append(f_table)

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Report_Card_{student.student_id}.pdf"'
    return response

@login_required
def generate_transcript(request, student_id):
    """Generates a full history academic transcript."""
    student = get_object_or_404(Student, id=student_id)
    config = get_institutional_metadata()
    results = Result.objects.filter(student=student).select_related('subject')
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    story.append(Paragraph(f"{config.name} - OFFICIAL TRANSCRIPT", styles['Title']))
    story.append(Paragraph(f"Student: {student.user.get_full_name()} | ID: {student.student_id}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Simple table for transcript history
    data = [['Subject', 'Date', 'Type', 'Final Score']]
    for r in results:
        data.append([r.subject.name, r.date.strftime('%Y'), r.exam_type.upper(), f"{r.score}/{r.max_score}"])
        
    t_table = Table(data, colWidths=[150, 80, 100, 100])
    t_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke)
    ]))
    story.append(t_table)
    
    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Transcript_{student.student_id}.pdf"'
    return response

def _generate_performance_report(request, start_date, end_date):
    """Generate performance analysis report"""
    user = request.user

    if user.role == 'student':
        student = _get_or_create_student(request.user)
        performance_data = _calculate_student_performance(student)
        predictions = _generate_grade_predictions(student)

        # Generate Premium PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        styles = getSampleStyleSheet()
        
        # Custom Premium Styles
        styles.add(ParagraphStyle(name='PremiumTitle', fontSize=24, fontName='Helvetica-Bold', alignment=1, spaceAfter=2, textColor=colors.HexColor('#0F172A')))
        styles.add(ParagraphStyle(name='PremiumSub', fontSize=10, fontName='Helvetica-Bold', alignment=1, spaceAfter=20, textColor=colors.HexColor('#64748B')))
        styles.add(ParagraphStyle(name='SectionHead', fontSize=14, fontName='Helvetica-Bold', spaceBefore=20, spaceAfter=10, textColor=colors.HexColor('#1E293B'), borderPadding=5, leftIndent=0))
        styles.add(ParagraphStyle(name='MetricLabel', fontSize=9, fontName='Helvetica-Bold', textColor=colors.HexColor('#4361EE')))
        styles.add(ParagraphStyle(name='MetricVal', fontSize=18, fontName='Helvetica-Bold', textColor=colors.HexColor('#0F172A')))

        story = []

        # 1. Institutional Header
        config = get_institutional_metadata()
        story.append(Paragraph(config.name.upper(), styles['PremiumTitle']))
        story.append(Paragraph("STRATEGIC PERFORMANCE ANALYSIS PROTOCOL", styles['PremiumSub']))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#4361EE'), spaceAfter=20))

        # 2. Performance Matrix
        id_data = [
            [Paragraph("STUDENT IDENTITY", styles['MetricLabel']), Paragraph("ANALYSIS WINDOW", styles['MetricLabel'])],
            [Paragraph(student.user.get_full_name(), styles['MetricVal']), Paragraph(f"{start_date} → {end_date}", styles['MetricVal'])]
        ]
        id_table = Table(id_data, colWidths=[240, 240])
        id_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 10)]))
        story.append(id_table)
        story.append(Spacer(1, 20))

        # 3. GPA Dynamics
        story.append(Paragraph("I. ACADEMIC VELOCITY (GPA)", styles['SectionHead']))
        gpa_data = [
            [Paragraph("CURRENT GPA", styles['MetricLabel']), Paragraph("OVERALL MASTERY", styles['MetricLabel'])],
            [Paragraph(f"{performance_data['gpa']:.2f}", styles['MetricVal']), Paragraph(f"{performance_data['overall_percentage']:.1f}%", styles['MetricVal'])]
        ]
        gpa_table = Table(gpa_data, colWidths=[240, 240])
        gpa_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
        story.append(gpa_table)
        story.append(Spacer(1, 15))

        # 4. Subject Analytics Matrix
        story.append(Paragraph("II. CURRICULAR PERFORMANCE CLUSTERS", styles['SectionHead']))
        if performance_data['subject_performance']:
            data = [['DOMAIN CLUSTER', 'AVERAGE SCORE', 'GRADE POINTS', 'STATUS']]
            for subj in performance_data['subject_performance']:
                gp = subj['grade_points']
                status = "EXCELLENT" if gp >= 3.5 else "PROFICIENT" if gp >= 3.0 else "DEVELOPING" if gp >= 2.0 else "CRITICAL"
                data.append([
                    subj['subject'].name.upper(),
                    f"{subj['average_score']:.1f}",
                    f"{gp:.2f}",
                    status
                ])

            table = Table(data, colWidths=[180, 100, 100, 100])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
            ]))
            story.append(table)
        
        story.append(Spacer(1, 25))

        # 5. Strategic Grade Predictions
        story.append(Paragraph("III. PREDICTIVE OUTCOME ANALYSIS", styles['SectionHead']))
        if predictions:
            data = [['SUBJECT PROTOCOL', 'CURR. AVG', 'PREDICTED', 'CONFIDENCE']]
            for pred in predictions:
                data.append([
                    pred['subject'].name.upper(),
                    f"{pred['current_average']:.1f}%",
                    f"{pred['predicted_score']:.1f}%",
                    f"{pred['confidence']:.1%}"
                ])

            table = Table(data, colWidths=[180, 100, 100, 100])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4361EE')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
            ]))
            story.append(table)

        # 6. Certification Footer
        story.append(Spacer(1, 60))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1')))
        story.append(Spacer(1, 10))
        
        footer_data = [
            [draw_institutional_seal(), "CERTIFIED ANALYTICS PROTOCOL GENERATED VIA NEXUS PROTOCOL"],
            ["", f"TIMESTAMP: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"]
        ]
        footer_table = Table(footer_data, colWidths=[100, 380])
        footer_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTSIZE', (0,1), (-1,1), 7),
            ('TEXTCOLOR', (0,1), (-1,1), colors.grey)
        ]))
        story.append(footer_table)

        # Build PDF
        doc.build(story)
        buffer.seek(0)

        # Create response
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="nexus_performance_{student.user.username}.pdf"'
        return response


    # For teachers/admins, generate class performance report
    return _generate_class_performance_report(request, start_date, end_date)

def _generate_class_performance_report(request, start_date, end_date):
    """Generate class performance report for teachers/admins"""
    # This would generate a comprehensive class report
    # For now, return a simple message
    messages.info(request, 'Class performance reports are being generated. This feature is under development.')
    return redirect('analytics_dashboard')