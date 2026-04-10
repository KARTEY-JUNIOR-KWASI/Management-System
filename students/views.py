from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from datetime import date, timedelta
from accounts.decorators import student_required
from core.models import Result, Subject, Attendance, Assignment, Submission
from .models import Student
from analytics.views import (
    _calculate_student_performance, _generate_grade_predictions,
    _generate_progress_report
)

def _get_or_create_student(user):
    student, created = Student.objects.get_or_create(
        user=user,
        defaults={
            'student_id': f'STUD{user.id:05d}',
        }
    )
    return student

@student_required
def student_dashboard(request):
    from analytics.views import _calculate_student_performance, _generate_grade_predictions
    from analytics.models import LearningInsight
    
    student = _get_or_create_student(request.user)
    
    # Advanced analytics data
    performance_data = _calculate_student_performance(student)
    predictions = _generate_grade_predictions(student)
    
    chart_predictions = [
        {
            'subject_name': p['subject'].name,
            'current_average': float(p['current_average']),
            'predicted_score': float(p['predicted_score'])
        }
        for p in predictions
    ]
    
    insights = LearningInsight.objects.filter(student=student, is_active=True)[:3]
    
    # Upcoming Assignments
    upcoming_assignments = Assignment.objects.filter(
        class_assigned=student.class_enrolled,
        due_date__gte=date.today()
    ).order_by('due_date')[:5]

    actions_data = [
        {'url': reverse('view_grades'), 'icon': 'bar-chart-3', 'label': 'Grades', 'desc': 'Academic performance', 'icon_bg': 'rgba(79, 70, 229, 0.1)', 'icon_color': '#4f46e5'},
        {'url': reverse('view_attendance'), 'icon': 'scan-line', 'label': 'Attendance', 'desc': 'Presence analytics', 'icon_bg': 'rgba(16, 185, 129, 0.1)', 'icon_color': '#10b981'},
        {'url': reverse('view_assignments'), 'icon': 'clipboard-list', 'label': 'Assignments', 'desc': 'Active objectives', 'icon_bg': 'rgba(245, 158, 11, 0.1)', 'icon_color': '#f59e0b'},
        {'url': reverse('student_timetable'), 'icon': 'calendar', 'label': 'Timetable', 'desc': 'Schedule overview', 'icon_bg': 'rgba(14, 165, 233, 0.1)', 'icon_color': '#0ea5e9'},
    ]

    context = {
        'student': student,
        'attendance_percentage': performance_data.get('attendance_rate', 0),
        'gpa': performance_data.get('gpa', 0),
        'performance_data': performance_data,
        'predictions': predictions,
        'chart_predictions': chart_predictions,
        'insights': insights,
        'upcoming_assignments': upcoming_assignments,
        'actions_data': actions_data,
    }
    return render(request, 'students/dashboard.html', context)

@student_required
def view_grades(request):
    student = _get_or_create_student(request.user)

    # Get all results for this student
    results = Result.objects.filter(student=student).select_related('subject').order_by('subject__name', '-date')

    # Group results by subject
    grades_by_subject = {}
    for result in results:
        subject_name = result.subject.name
        if subject_name not in grades_by_subject:
            grades_by_subject[subject_name] = {
                'subject': result.subject,
                'results': [],
                'average': 0,
                'grade_points': 0
            }
        grades_by_subject[subject_name]['results'].append(result)

    # Calculate averages for each subject
    for subject_data in grades_by_subject.values():
        if subject_data['results']:
            total_percentage = sum((r.score / r.max_score * 100) for r in subject_data['results'])
            subject_data['average'] = total_percentage / len(subject_data['results'])
            # Convert to grade points (4.0 scale)
            subject_data['grade_points'] = min(4.0, subject_data['average'] / 25)

    # Calculate overall GPA centrally
    overall_gpa = student.gpa

    context = {
        'student': student,
        'grades_by_subject': grades_by_subject,
        'overall_gpa': overall_gpa,
    }
    return render(request, 'students/view_grades.html', context)

@student_required
def view_attendance(request):
    student = _get_or_create_student(request.user)

    # Get all attendance records for this student
    attendance_records = Attendance.objects.filter(student=student).select_related('class_attended').order_by('-date')

    # Calculate attendance statistics
    total_days = attendance_records.count()
    present_days = attendance_records.filter(status='present').count()
    absent_days = attendance_records.filter(status='absent').count()
    late_days = attendance_records.filter(status='late').count()

    attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0

    from django.db.models import Count, Q
    from django.db.models.functions import TruncMonth

    monthly_attendance = attendance_records.annotate(
        month=TruncMonth('date')
    ).values('month').annotate(
        total=Count('id'),
        present=Count('id', filter=Q(status='present')),
        absent=Count('id', filter=Q(status='absent')),
        late=Count('id', filter=Q(status='late'))
    ).order_by('-month')

    context = {
        'student': student,
        'attendance_records': attendance_records[:30],  # Last 30 records
        'total_days': total_days,
        'present_days': present_days,
        'absent_days': absent_days,
        'late_days': late_days,
        'attendance_percentage': attendance_percentage,
        'monthly_attendance': monthly_attendance,
    }
    return render(request, 'students/view_attendance.html', context)

@student_required
def view_assignments(request):
    student = _get_or_create_student(request.user)

    # Get assignments for this student's class
    assignments = Assignment.objects.filter(class_assigned=student.class_enrolled).select_related('subject', 'teacher').order_by('-due_date')

    # Get submissions for this student
    submissions = Submission.objects.filter(student=student).select_related('assignment')

    # Create a dictionary of submissions keyed by assignment id
    submission_dict = {sub.assignment.id: sub for sub in submissions}

    # Add submission status to assignments
    for assignment in assignments:
        assignment.submission = submission_dict.get(assignment.id)
        if assignment.submission:
            assignment.status = 'submitted'
        elif assignment.due_date >= date.today():
            assignment.status = 'pending'
        else:
            assignment.status = 'overdue'

    context = {
        'student': student,
        'assignments': assignments,
    }
    return render(request, 'students/view_assignments.html', context)

@student_required
def submit_assignment(request, assignment_id):
    student = _get_or_create_student(request.user)

    assignment = get_object_or_404(Assignment, id=assignment_id, class_assigned=student.class_enrolled)

    # Check if already submitted
    existing_submission = Submission.objects.filter(assignment=assignment, student=student).first()

    if request.method == 'POST':
        if existing_submission:
            messages.error(request, 'You have already submitted this assignment.')
            return redirect('view_assignments')

        file = request.FILES.get('file')
        if not file:
            messages.error(request, 'Please select a file to submit.')
            return redirect('submit_assignment', assignment_id=assignment_id)

        # Create submission
        submission = Submission.objects.create(
            assignment=assignment,
            student=student,
            file=file
        )

        messages.success(request, 'Assignment submitted successfully!')
        return redirect('view_assignments')

    context = {
        'student': student,
        'assignment': assignment,
        'existing_submission': existing_submission,
    }
    return render(request, 'students/submit_assignment.html', context)

@student_required
def student_timetable(request):
    from core.models import Timetable
    
    student = get_object_or_404(Student, user=request.user)
    
    timetables = []
    if student.class_enrolled:
        timetables = Timetable.objects.filter(class_assigned=student.class_enrolled).select_related('subject', 'teacher').order_by('start_time')

    DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']

    schedule_dict = {day: [] for day in DAYS}
    for t in timetables:
        if t.day in schedule_dict:
            schedule_dict[t.day].append(t)
            
    schedule_list = [(day.capitalize(), schedule_dict[day]) for day in DAYS]

    context = {
        'schedule_list': schedule_list,
        'student': student,
    }
    return render(request, 'students/timetable.html', context)


@student_required
def download_report_card_pdf(request):
    """
    Standalone view to download the PDF report card.
    Defaults to the last 90 days if no dates specified.
    """
    end_date = request.GET.get('end_date', date.today().isoformat())
    start_date = request.GET.get('start_date', (date.today() - timedelta(days=90)).isoformat())
    
    return _generate_progress_report(request, start_date, end_date)
