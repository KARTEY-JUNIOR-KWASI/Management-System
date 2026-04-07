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
from datetime import datetime, timedelta, date
import json
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

from .models import Notification, PerformanceAnalytics, SystemAnalytics, AutomatedReport, LearningInsight
from students.models import Student
from teachers.models import Teacher
from core.models import Subject, Class, Result, Attendance, Assignment, Submission
from accounts.models import User


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


def _get_or_create_student(user):
    student, created = Student.objects.get_or_create(
        user=user,
        defaults={
            'student_id': f'STD{user.id:05d}',
        }
    )
    return student

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
    # Generate system analytics if not exists for today
    today = date.today()
    system_analytics, created = SystemAnalytics.objects.get_or_create(
        date=today,
        defaults=_calculate_system_analytics()
    )

    # Get recent notifications
    recent_notifications = Notification.objects.filter(
        created_at__gte=today - timedelta(days=7)
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
    recent_notifications = Notification.objects.filter(
        recipient=request.user,
        created_at__gte=date.today() - timedelta(days=7)
    ).order_by('-created_at')[:5]

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
    insights = LearningInsight.objects.filter(
        student=student,
        is_active=True
    ).order_by('-confidence_score')[:5]

    # Grade predictions
    predictions = _generate_grade_predictions(student)

    # Recent notifications
    recent_notifications = Notification.objects.filter(
        recipient=request.user,
        created_at__gte=date.today() - timedelta(days=7)
    ).order_by('-created_at')[:5]

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

        recipient_objects = []
        for recipient_id in recipients:
            recipient = get_object_or_404(User, id=recipient_id)
            Notification.objects.create(
                recipient=recipient,
                notification_type=notification_type,
                title=title,
                message=message,
                priority=priority
            )
            recipient_objects.append(recipient)

        # Send email notifications if configured
        # Pass the actual User objects so helper can access .email attribute
        _send_email_notifications(title, message, recipient_objects)

        messages.success(request, f'Notification sent to {len(recipients)} recipients!')
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
    notifications.filter(is_read=False).update(is_read=True)

    context = {
        'notifications': notifications,
        'unread_count': unread_count,
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
    
    return {
        **core_counts,
        'overall_attendance_rate': overall_attendance_rate,
        'average_gpa': average_gpa,
        'assignment_completion_rate': assignment_completion_rate,
        'total_at_risk': len(at_risk_students),
        'critical_cases': len([s for s in at_risk_students if s['risk_level'] == 'critical']),
        'at_risk_list': at_risk_students[:10], # Include top 10 for dashboard
    }

    # Attendance trend
    attendance_trend = _calculate_attendance_trend()

    return {
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_classes': total_classes,
        'total_subjects': total_subjects,
        'overall_attendance_rate': overall_attendance_rate,
        'attendance_trend': attendance_trend,
        'average_gpa': average_gpa,
        'assignment_completion_rate': assignment_completion_rate,
        'students_at_risk': students_at_risk,
        'critical_cases': critical_cases,
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

        # Average GPA for this class in one aggregate query
        avg_score = Result.objects.filter(student__in=students_in_class).aggregate(avg=Avg('score'))['avg'] or 0
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
            recent_results = Result.objects.filter(student=student).order_by('-date')[:3]
            if len(recent_results) >= 2:
                scores = [r.score for r in recent_results]
                if scores[0] < scores[-1] - 10:  # Declining by more than 10 points
                    insights.append({
                        'student': student,
                        'type': 'performance_decline',
                        'message': f'{student.user.get_full_name()} shows declining performance',
                        'severity': 'high',
                    })

            recent_attendance = Attendance.objects.filter(
                student=student,
                class_attended=class_obj
            ).order_by('-date')[:5]

            absent_count = recent_attendance.filter(status='absent').count()
            if absent_count >= 3:
                insights.append({
                    'student': student,
                    'type': 'attendance_concern',
                    'message': f'{student.user.get_full_name()} has been absent {absent_count} times recently',
                    'severity': 'medium',
                })

    return insights[:10]  # Return top 10 insights

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

def _calculate_student_performance(student):
    """
    Calculate detailed performance metrics for a student.
    Optimized with fixed initialization and better querying.
    """
    # GPA calculation
    results = Result.objects.filter(student=student).select_related('subject')
    if results.exists():
        total_score = sum(r.score for r in results)
        max_possible = sum(r.max_score for r in results)
        overall_percentage = (total_score / max_possible * 100) if max_possible > 0 else 0
        gpa = min(4.0, overall_percentage / 25)
    else:
        gpa = 0
        overall_percentage = 0

    # Subject-wise performance
    subject_performance = []  # Fixed: Initialized the list
    subject_ids = Assignment.objects.filter(class_assigned=student.class_enrolled).values_list('subject_id', flat=True).distinct()
    subjects = Subject.objects.filter(id__in=subject_ids)
    
    for subject in subjects:
        subject_results = [r for r in results if r.subject_id == subject.id]
        if subject_results:
            subject_avg = sum(r.score for r in subject_results) / len(subject_results)
            subject_performance.append({
                'subject': subject,
                'average_score': subject_avg,
                'grade_points': min(4.0, subject_avg / 25),
            })

    # Attendance analysis
    attendance_stats = Attendance.objects.filter(student=student).aggregate(
        total=Count('id'),
        present=Count('id', filter=Q(status='present'))
    )
    total_days = attendance_stats['total']
    attendance_rate = (attendance_stats['present'] / total_days * 100) if total_days > 0 else 0

    # Assignment completion
    assignments = Assignment.objects.filter(class_assigned=student.class_enrolled)
    assignment_count = assignments.count()
    if assignment_count > 0:
        submission_count = Submission.objects.filter(student=student, assignment__in=assignments).count()
        completion_rate = (submission_count / assignment_count * 100)
    else:
        completion_rate = 0
        submission_count = 0

    return {
        'gpa': gpa,
        'overall_percentage': overall_percentage,
        'subject_performance': subject_performance,
        'attendance_rate': attendance_rate,
        'assignment_completion_rate': completion_rate,
        'total_assignments': assignment_count,
        'completed_assignments': submission_count,
    }

def _generate_grade_predictions(student):
    """Generate grade predictions based on current performance"""
    predictions = []

    subject_ids = Assignment.objects.filter(class_assigned=student.class_enrolled).values_list('subject_id', flat=True).distinct()
    subjects = Subject.objects.filter(id__in=subject_ids)
    for subject in subjects:
        # Get recent performance data
        recent_results = Result.objects.filter(
            student=student,
            subject=subject
        ).order_by('-date')[:5]

        if recent_results.exists():
            avg_recent_score = recent_results.aggregate(avg=Avg('score'))['avg'] or 0

            # Simple prediction based on trend and attendance
            attendance_records = Attendance.objects.filter(
                student=student,
                class_attended=subject.class_assigned
            ).order_by('-date')[:10]

            attendance_rate = (attendance_records.filter(status='present').count() / attendance_records.count() * 100) if attendance_records.exists() else 100

            # Prediction algorithm (simplified)
            base_prediction = avg_recent_score
            attendance_bonus = (attendance_rate - 80) * 0.5  # Bonus/penalty based on attendance
            predicted_score = min(100, max(0, base_prediction + attendance_bonus))

            confidence = min(0.9, len(recent_results) / 10)  # Higher confidence with more data

            predictions.append({
                'subject': subject,
                'current_average': avg_recent_score,
                'predicted_score': predicted_score,
                'confidence': confidence,
                'attendance_impact': attendance_bonus,
            })

    return predictions

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
    """Generate student progress report"""
    if request.user.role != 'student':
        return _redirect_wrong_role(request, 'student')

    student = _get_or_create_student(request.user)

    # Get data for the period
    results = Result.objects.filter(
        student=student,
        date__range=(start_date, end_date)
    ).select_related('subject')

    attendance = Attendance.objects.filter(
        student=student,
        date__range=(start_date, end_date)
    )

    assignments = Assignment.objects.filter(
        class_assigned=student.class_enrolled,
        due_date__range=(start_date, end_date)
    )

    submissions = Submission.objects.filter(
        student=student,
        assignment__in=assignments
    )

    # Generate PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title = Paragraph(f"Progress Report - {student.user.get_full_name()}", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))

    # Period
    period_text = f"Period: {start_date} to {end_date}"
    story.append(Paragraph(period_text, styles['Normal']))
    story.append(Spacer(1, 12))

    # Academic Performance
    story.append(Paragraph("Academic Performance", styles['Heading2']))
    if results.exists():
        data = [['Subject', 'Score', 'Max Score', 'Percentage', 'Date']]
        for result in results:
            percentage = f"{(result.score / result.max_score * 100):.1f}%" if result.max_score > 0 else "N/A"
            data.append([
                result.subject.name,
                str(result.score),
                str(result.max_score),
                percentage,
                result.date.strftime('%Y-%m-%d')
            ])

        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("No academic results found for this period.", styles['Normal']))

    story.append(Spacer(1, 12))

    # Attendance Summary
    story.append(Paragraph("Attendance Summary", styles['Heading2']))
    total_days = attendance.count()
    present_days = attendance.filter(status='present').count()
    attendance_rate = (present_days / total_days * 100) if total_days > 0 else 0

    attendance_text = f"Total Days: {total_days}, Present: {present_days}, Attendance Rate: {attendance_rate:.1f}%"
    story.append(Paragraph(attendance_text, styles['Normal']))

    story.append(Spacer(1, 12))

    # Assignment Completion
    story.append(Paragraph("Assignment Completion", styles['Heading2']))
    total_assignments = assignments.count()
    completed_assignments = submissions.count()
    completion_rate = (completed_assignments / total_assignments * 100) if total_assignments > 0 else 0

    assignment_text = f"Total Assignments: {total_assignments}, Completed: {completed_assignments}, Completion Rate: {completion_rate:.1f}%"
    story.append(Paragraph(assignment_text, styles['Normal']))

    # Build PDF
    doc.build(story)
    buffer.seek(0)

    # Create response
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="progress_report_{student.user.username}_{start_date}_{end_date}.pdf"'
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

    # Generate PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_para = Paragraph(title, styles['Title'])
    story.append(title_para)
    story.append(Spacer(1, 12))

    # Attendance data
    if attendance.exists():
        data = [['Date', 'Student', 'Class', 'Status']]
        for record in attendance:
            data.append([
                record.date.strftime('%Y-%m-%d'),
                record.student.user.get_full_name(),
                record.class_attended.name,
                record.status.title()
            ])

        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("No attendance records found for this period.", styles['Normal']))

    # Build PDF
    doc.build(story)
    buffer.seek(0)

    # Create response
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    filename = f"attendance_report_{start_date}_{end_date}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def _generate_performance_report(request, start_date, end_date):
    """Generate performance analysis report"""
    user = request.user

    if user.role == 'student':
        student = _get_or_create_student(request.user)
        performance_data = _calculate_student_performance(student)
        predictions = _generate_grade_predictions(student)

        # Generate PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Title
        title = Paragraph(f"Performance Analysis - {student.user.get_full_name()}", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 12))

        # Overall Performance
        story.append(Paragraph("Overall Performance", styles['Heading2']))
        overall_text = f"GPA: {performance_data['gpa']:.2f}, Overall Percentage: {performance_data['overall_percentage']:.1f}%"
        story.append(Paragraph(overall_text, styles['Normal']))
        story.append(Spacer(1, 12))

        # Subject Performance
        story.append(Paragraph("Subject-wise Performance", styles['Heading2']))
        if performance_data['subject_performance']:
            data = [['Subject', 'Average Score', 'Grade Points']]
            for subj in performance_data['subject_performance']:
                data.append([
                    subj['subject'].name,
                    f"{subj['average_score']:.1f}",
                    f"{subj['grade_points']:.2f}"
                ])

            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(table)
        story.append(Spacer(1, 12))

        # Predictions
        story.append(Paragraph("Grade Predictions", styles['Heading2']))
        if predictions:
            data = [['Subject', 'Current Average', 'Predicted Score', 'Confidence']]
            for pred in predictions:
                data.append([
                    pred['subject'].name,
                    f"{pred['current_average']:.1f}",
                    f"{pred['predicted_score']:.1f}",
                    f"{pred['confidence']:.1%}"
                ])

            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(table)

        # Build PDF
        doc.build(story)
        buffer.seek(0)

        # Create response
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="performance_report_{student.user.username}_{start_date}_{end_date}.pdf"'
        return response

    # For teachers/admins, generate class performance report
    return _generate_class_performance_report(request, start_date, end_date)

def _generate_class_performance_report(request, start_date, end_date):
    """Generate class performance report for teachers/admins"""
    # This would generate a comprehensive class report
    # For now, return a simple message
    messages.info(request, 'Class performance reports are being generated. This feature is under development.')
    return redirect('analytics_dashboard')