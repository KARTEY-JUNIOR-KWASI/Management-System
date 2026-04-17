from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from functools import wraps
from students.models import Student
from teachers.models import Teacher
from core.models import Class, Subject, Attendance, Result, Assignment, Submission, AuditLog, NoticeBoard, House, HousePointLog
from .forms import StudentForm, TeacherForm, SubjectForm, ClassForm
from django.core.paginator import Paginator

from accounts.decorators import admin_required

from django.db.models import Count, Q, Avg, F, Sum
from finance.models import Invoice, Payment
from analytics.views import _calculate_system_analytics, _calculate_performance_trend, _identify_at_risk_students

@admin_required
def admin_dashboard(request):
    system_analytics = _calculate_system_analytics()
    performance_trend = _calculate_performance_trend()
    at_risk_students = _identify_at_risk_students()
    
    # Financial Pulse for Main Dashboard
    total_expected = Invoice.objects.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    total_collected = Payment.objects.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
    collection_percentage = (total_collected / total_expected * 100) if total_expected > 0 else 0
    
    total_students = system_analytics.get('total_students', 0)
    total_teachers = system_analytics.get('total_teachers', 0)
    total_classes = system_analytics.get('total_classes', 0)
    total_subjects = system_analytics.get('total_subjects', 0)
    
    attendance_stats = system_analytics.get('overall_attendance_rate', 0)
    
    students = Student.objects.with_performance_stats().select_related('user', 'class_enrolled').order_by('-user__date_joined')[:10]
    
    actions_data = [
        {'url': reverse('student_list'), 'icon': 'users', 'label': 'Students', 'desc': 'Manage student records', 'icon_bg': 'rgba(79, 70, 229, 0.1)', 'icon_color': '#4f46e5'},
        {'url': reverse('teacher_list'), 'icon': 'briefcase', 'label': 'Teachers', 'desc': 'Staff operations', 'icon_bg': 'rgba(16, 185, 129, 0.1)', 'icon_color': '#10b981'},
        {'url': reverse('class_list'), 'icon': 'layout-grid', 'label': 'Classes', 'desc': 'Academic sectors', 'icon_bg': 'rgba(245, 158, 11, 0.1)', 'icon_color': '#f59e0b'},
        {'url': reverse('subject_list'), 'icon': 'book-open', 'label': 'Subjects', 'desc': 'Curriculum domains', 'icon_bg': 'rgba(239, 68, 68, 0.1)', 'icon_color': '#ef4444'},
        {'url': reverse('finance:finance_hub'), 'icon': 'wallet', 'label': 'Finance', 'desc': 'Revenue intelligence', 'icon_bg': 'rgba(99, 102, 241, 0.1)', 'icon_color': '#6366f1'},
        {'url': reverse('manage_timetable'), 'icon': 'calendar', 'label': 'Timetable', 'desc': 'Schedule management', 'icon_bg': 'rgba(14, 165, 233, 0.1)', 'icon_color': '#0ea5e9'},
    ]

    context = {
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_classes': total_classes,
        'total_subjects': total_subjects,
        'attendance_stats': attendance_stats,
        'attendance_trend': system_analytics.get('attendance_trend', 'stable'),
        'performance_trend': performance_trend,
        'at_risk_students': at_risk_students[:5],
        'total_at_risk': len(at_risk_students),
        'students': students,
        'system_analytics': system_analytics,
        'recent_logs': AuditLog.objects.select_related('user').all()[:10],
        'notices': NoticeBoard.objects.select_related('author').all()[:5],
        'total_revenue_expected': total_expected,
        'total_revenue_collected': total_collected,
        'collection_percentage': round(collection_percentage, 1),
        'actions_data': actions_data,
    }
    return render(request, 'admin_dashboard/dashboard.html', context)

@admin_required
def student_list(request):
    from django.db.models import Q
    
    students_query = Student.objects.with_performance_stats().select_related('user', 'class_enrolled').order_by('-user__date_joined')
    classes = Class.objects.all().order_by('name')

    q = request.GET.get('q', '').strip()
    class_id = request.GET.get('class', '')

    if q:
        students_query = students_query.filter(
            Q(student_id__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q)
        )
    if class_id:
        students_query = students_query.filter(class_enrolled_id=class_id)
        
    paginator = Paginator(students_query, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'students': page_obj, 
        'page_obj': page_obj,
        'classes': classes,
        'q': q,
        'selected_class': class_id,
        'total_students': students_query.count()
    }
    return render(request, 'admin_dashboard/students.html', context)

@admin_required
def create_notice(request):
    """Institutional announcement creation engine."""
    if request.method == 'POST':
        title = request.POST.get('title')
        category = request.POST.get('category')
        content = request.POST.get('content')
        is_pinned = request.POST.get('is_pinned') == 'on'

        if title and content:
            notice = NoticeBoard.objects.create(
                title=title,
                category=category,
                content=content,
                is_pinned=is_pinned,
                author=request.user
            )
            
            # Dispatch notifications to ALL users for institutional awareness
            from accounts.models import User
            from core.models import Notification
            
            users = User.objects.all()
            notifications = [
                Notification(
                    recipient=u,
                    notification_type='announcement',
                    title=f"New Notice: {title}",
                    message=content[:100],
                    priority='high' if is_pinned else 'medium'
                ) for u in users
            ]
            Notification.objects.bulk_create(notifications)
            
            messages.success(request, 'Notice published and dispatched to all school protocols.')
        else:
            messages.error(request, 'Failed to publish notice. Title and content are required.')
            
    return redirect('admin_dashboard')

@admin_required
def student_create(request):
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save()
            msg = f'Student {student.user.get_full_name()} created successfully.'
            # Logic to extract credentials from form OR instance
            username = getattr(form, 'generated_username', getattr(student, '_generated_username', None))
            password = getattr(form, 'generated_password', getattr(student, '_generated_password', None))
            
            if username and password:
                msg += f' [Student ID: {username}] [Password: {password}]'
            
            if hasattr(form.instance, '_parent_generated_password'):
                p_username = getattr(form.instance, '_parent_generated_username', 'N/A')
                p_password = getattr(form.instance, '_parent_generated_password', 'N/A')
                msg += f' | [Guardian ID: {p_username}] [Password: {p_password}]'
                
            messages.success(request, msg)
            return redirect('student_list')
    else:
        form = StudentForm()
    return render(request, 'admin_dashboard/student_form.html', {'form': form})

@admin_required
def student_update(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            messages.success(request, 'Student updated successfully')
            return redirect('student_list')
    else:
        form = StudentForm(instance=student)
    return render(request, 'admin_dashboard/student_form.html', {'form': form})

@admin_required
def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        student.user.delete()
        messages.success(request, 'Student deleted successfully')
        return redirect('student_list')
    return render(request, 'admin_dashboard/student_confirm_delete.html', {'student': student})

@admin_required
def student_detail(request, pk):
    student = get_object_or_404(Student.objects.select_related('user', 'class_enrolled'), pk=pk)

    # Results data with filtering
    subject_filter = request.GET.get('subject', '')
    exam_type_filter = request.GET.get('exam_type', '')

    all_results = Result.objects.filter(student=student).select_related('subject').order_by('-date')

    if subject_filter:
        all_results = all_results.filter(subject__name__icontains=subject_filter)
    if exam_type_filter:
        all_results = all_results.filter(exam_type__icontains=exam_type_filter)

    recent_results = list(all_results[:10])
    for result in recent_results:
        result.result_percentage = (result.score / result.max_score * 100) if result.max_score and result.max_score != 0 else 0

    # Attendance data
    attendance_records = Attendance.objects.filter(student=student).order_by('-date')[:10]
    attendance_stats = Attendance.objects.filter(student=student).aggregate(
        total=Count('id'),
        present=Count('id', filter=Q(status='present')),
        absent=Count('id', filter=Q(status='absent')),
        late=Count('id', filter=Q(status='late'))
    )
    total_days = attendance_stats['total']
    present_days = attendance_stats['present']
    absent_days = attendance_stats['absent']
    late_days = attendance_stats['late']
    attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0

    # Performance analytics
    average_score = 0
    highest_score = 0
    lowest_score = 100
    subject_performance = {}

    if all_results.exists():
        scores = [(r.score / r.max_score * 100) for r in all_results]
        average_score = sum(scores) / len(scores)
        highest_score = max(scores)
        lowest_score = min(scores)

        # Subject-wise performance
        for result in all_results:
            subject_name = result.subject.name
            percentage = (result.score / result.max_score * 100) if result.max_score else 0
            if subject_name not in subject_performance:
                subject_performance[subject_name] = {'scores': [], 'average': 0}
            subject_performance[subject_name]['scores'].append(percentage)

        for subject, data in subject_performance.items():
            data['average'] = sum(data['scores']) / len(data['scores'])

    # Assignments and submissions
    assignments = Assignment.objects.filter(class_assigned=student.class_enrolled).select_related('subject', 'teacher').order_by('-due_date')[:10]
    assignment_status = []

    # Map submissions by assignment_id in one query to avoid N+1
    student_submissions = Submission.objects.filter(assignment__in=assignments, student=student)
    submission_map = {s.assignment_id: s for s in student_submissions}

    for assignment in assignments:
        submission = submission_map.get(assignment.id)
        status = {
            'assignment': assignment,
            'submitted': submission is not None,
            'submission': submission,
            'on_time': submission and submission.submitted_at.date() <= assignment.due_date if submission else False,
            'late': submission and submission.submitted_at.date() > assignment.due_date if submission else False,
        }
        assignment_status.append(status)

    # Performance insights
    performance_insights = []
    if average_score > 0:
        if average_score >= 90:
            performance_insights.append("Excellent academic performance!")
        elif average_score >= 80:
            performance_insights.append("Very good academic performance.")
        elif average_score >= 70:
            performance_insights.append("Good academic performance.")
        elif average_score >= 60:
            performance_insights.append("Satisfactory performance. Room for improvement.")
        else:
            performance_insights.append("Needs significant improvement in academic performance.")

    if attendance_percentage >= 95:
        performance_insights.append("Excellent attendance record.")
    elif attendance_percentage >= 85:
        performance_insights.append("Good attendance record.")
    elif attendance_percentage >= 75:
        performance_insights.append("Fair attendance. Consider improving regularity.")
    else:
        performance_insights.append("Poor attendance. Immediate attention required.")

    # Recent activity (last 30 days)
    from datetime import datetime, timedelta
    thirty_days_ago = datetime.now().date() - timedelta(days=30)
    recent_activity = {
        'results': Result.objects.filter(student=student, date__gte=thirty_days_ago).count(),
        'attendance': Attendance.objects.filter(student=student, date__gte=thirty_days_ago).count(),
        'submissions': Submission.objects.filter(student=student, submitted_at__date__gte=thirty_days_ago).count(),
    }

    context = {
        'student': student,
        'recent_results': recent_results,
        'all_results': all_results,
        'attendance_records': attendance_records,
        'total_days': total_days,
        'present_days': present_days,
        'absent_days': absent_days,
        'late_days': late_days,
        'attendance_percentage': attendance_percentage,
        'average_score': average_score,
        'highest_score': highest_score,
        'lowest_score': lowest_score,
        'subject_performance': subject_performance,
        'assignment_status': assignment_status,
        'performance_insights': performance_insights,
        'recent_activity': recent_activity,
        'subject_filter': subject_filter,
        'exam_type_filter': exam_type_filter,
    }
    return render(request, 'admin_dashboard/student_detail.html', context)

@admin_required
def teacher_list(request):
    teachers_query = Teacher.objects.select_related('user').prefetch_related('subjects').all()
    paginator = Paginator(teachers_query, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_dashboard/teachers.html', {'teachers': page_obj, 'page_obj': page_obj})

@admin_required
def teacher_create(request):
    if request.method == 'POST':
        form = TeacherForm(request.POST, request.FILES)
        if form.is_valid():
            teacher = form.save()
            msg = f'Teacher {teacher.user.get_full_name()} created successfully.'
            # Logic to extract credentials from form OR instance
            username = getattr(form, 'generated_username', getattr(teacher, '_generated_username', None))
            password = getattr(form, 'generated_password', getattr(teacher, '_generated_password', None))
            
            if username and password:
                msg += f' [User ID: {username}] [Password: {password}]'
            messages.success(request, msg)
            return redirect('teacher_list')
    else:
        form = TeacherForm()
    return render(request, 'admin_dashboard/teacher_form.html', {'form': form})

@admin_required
def teacher_update(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    if request.method == 'POST':
        form = TeacherForm(request.POST, request.FILES, instance=teacher)
        if form.is_valid():
            form.save()
            messages.success(request, 'Teacher updated successfully')
            return redirect('teacher_list')
    else:
        form = TeacherForm(instance=teacher)
    return render(request, 'admin_dashboard/teacher_form.html', {'form': form})

@admin_required
def teacher_delete(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    if request.method == 'POST':
        teacher.user.delete()
        messages.success(request, 'Teacher deleted successfully')
        return redirect('teacher_list')
    return render(request, 'admin_dashboard/teacher_confirm_delete.html', {'teacher': teacher})

@admin_required
def teacher_detail(request, pk):
    teacher = get_object_or_404(Teacher.objects.select_related('user'), pk=pk)

    # Get teacher's assignments and classes
    assignments = Assignment.objects.filter(teacher=teacher.user).select_related('subject', 'class_assigned').order_by('-due_date')[:10]

    # Get classes taught by this teacher
    classes_taught = Class.objects.filter(assignments__teacher=teacher.user).distinct()

    # Get students taught by this teacher
    students_taught = Student.objects.filter(class_enrolled__assignments__teacher=teacher.user).distinct().count()

    # Get recent submissions for teacher's assignments
    recent_submissions = Submission.objects.filter(assignment__teacher=teacher.user).select_related('assignment', 'student__user').order_by('-submitted_at')[:10]

    # Assignment statistics
    total_assignments = Assignment.objects.filter(teacher=teacher.user).count()
    submitted_assignments = Submission.objects.filter(assignment__teacher=teacher.user).count()
    pending_assignments = total_assignments - submitted_assignments

    # Subject expertise
    subjects_taught = Subject.objects.filter(assignment_set__teacher=teacher.user).distinct()

    context = {
        'teacher': teacher,
        'assignments': assignments,
        'classes_taught': classes_taught,
        'students_taught': students_taught,
        'recent_submissions': recent_submissions,
        'total_assignments': total_assignments,
        'submitted_assignments': submitted_assignments,
        'pending_assignments': pending_assignments,
        'subjects_taught': subjects_taught,
    }
    return render(request, 'admin_dashboard/teacher_detail.html', context)

@admin_required
def subject_list(request):
    subjects_query = Subject.objects.all()
    paginator = Paginator(subjects_query, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_dashboard/subjects.html', {'subjects': page_obj, 'page_obj': page_obj})

@admin_required
def subject_create(request):
    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subject created successfully')
            return redirect('subject_list')
    else:
        form = SubjectForm()
    return render(request, 'admin_dashboard/subject_form.html', {'form': form})

@admin_required
def subject_update(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subject updated successfully')
            return redirect('subject_list')
    else:
        form = SubjectForm(instance=subject)
    return render(request, 'admin_dashboard/subject_form.html', {'form': form})

@admin_required
def subject_delete(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        subject.delete()
        messages.success(request, 'Subject deleted successfully')
        return redirect('subject_list')
    return render(request, 'admin_dashboard/subject_confirm_delete.html', {'subject': subject})

@admin_required
def class_list(request):
    classes_query = Class.objects.select_related('class_teacher').all()
    paginator = Paginator(classes_query, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_dashboard/classes.html', {'classes': page_obj, 'page_obj': page_obj})

@admin_required
def class_create(request):
    if request.method == 'POST':
        form = ClassForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Class created successfully')
            return redirect('class_list')
    else:
        form = ClassForm()
    return render(request, 'admin_dashboard/class_form.html', {'form': form})

@admin_required
def class_update(request, pk):
    class_obj = get_object_or_404(Class, pk=pk)
    if request.method == 'POST':
        form = ClassForm(request.POST, instance=class_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Class updated successfully')
            return redirect('class_list')
    else:
        form = ClassForm(instance=class_obj)
    return render(request, 'admin_dashboard/class_form.html', {'form': form})

@admin_required
def class_delete(request, pk):
    class_obj = get_object_or_404(Class, pk=pk)
    if request.method == 'POST':
        class_obj.delete()
        messages.success(request, 'Class deleted successfully')
        return redirect('class_list')
    return render(request, 'admin_dashboard/class_confirm_delete.html', {'class': class_obj})

@admin_required
def manage_timetable(request):
    from core.models import Timetable, Class
    from .forms import TimetableForm

    classes = Class.objects.all()
    selected_class_id = request.GET.get('class_id')
    selected_class = None
    timetables = []

    if selected_class_id:
        selected_class = get_object_or_404(Class, id=selected_class_id)
        timetables = Timetable.objects.filter(class_assigned=selected_class).order_by('start_time')

    if request.method == 'POST':
        form = TimetableForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Timetable entry added successfully.')
            except Exception as e:
                messages.error(request, f'Error adding entry: {str(e)}. Might be a duplicate time block.')
            redirect_url = f"{reverse('manage_timetable')}?class_id={form.cleaned_data['class_assigned'].id}"
            return redirect(redirect_url)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        initial = {'class_assigned': selected_class} if selected_class else {}
        form = TimetableForm(initial=initial)

    DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']

    # Group timetables by day for display
    schedule_dict = {day: [] for day in DAYS}
    for t in timetables:
        if t.day in schedule_dict:
            schedule_dict[t.day].append(t)
            
    schedule_list = [(day.capitalize(), schedule_dict[day]) for day in DAYS]

    context = {
        'classes': classes,
        'selected_class': selected_class,
        'schedule_list': schedule_list,
        'form': form
    }
    return render(request, 'admin_dashboard/manage_timetable.html', context)


@admin_required
def system_settings(request):
    """Institutional configuration management."""
    from core.models import SchoolConfiguration
    from .forms import SchoolSettingsForm
    
    config = SchoolConfiguration.get_config()
    
    if request.method == 'POST':
        form = SchoolSettingsForm(request.POST, request.FILES, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Institutional configuration deployed successfully.')
            return redirect('system_settings')
    else:
        form = SchoolSettingsForm(instance=config)
        
    return render(request, 'admin_dashboard/settings.html', {
        'form': form,
        'config': config
    })

@admin_required
def academic_diagnostics(request):
    """Institutional-level performance diagnostics."""
    from core.models import Result, Student, Class, Subject
    from django.db.models import Avg, Count
    
    # Grade Distribution
    results = Result.objects.all()
    distribution = {
        'Exemplary (90-100)': results.filter(score__gte=F('max_score') * 0.9).count(),
        'Proficient (75-89)': results.filter(score__gte=F('max_score') * 0.75, score__lt=F('max_score') * 0.9).count(),
        'Passing (50-74)': results.filter(score__gte=F('max_score') * 0.5, score__lt=F('max_score') * 0.75).count(),
        'Below Range (<50)': results.filter(score__lt=F('max_score') * 0.5).count(),
    }
    
    # Subject Performance
    subject_stats = Subject.objects.annotate(
        avg_score=Avg('result__score'),
        pass_count=Count('result', filter=Q(result__score__gte=F('result__max_score') * 0.5))
    ).order_by('-avg_score')

    # Class Performance
    class_stats = Class.objects.annotate(
        avg_score=Avg('assignments__submission__grade')
    ).order_by('-avg_score')

    return render(request, 'admin_dashboard/academic_diagnostics.html', {
        'distribution': distribution,
        'subject_stats': subject_stats,
        'class_stats': class_stats,
    })

@admin_required
def class_performance_analytics(request, class_id):
    """Deep-dive into class rankings and student positioning."""
    from core.models import Class
    from core.academic_utils import get_class_rankings
    
    target_class = get_object_or_404(Class, id=class_id)
    rankings = get_class_rankings(class_id)
    
    return render(request, 'admin_dashboard/class_rankings.html', {
        'target_class': target_class,
        'rankings': rankings
    })

@admin_required
def delete_timetable_entry(request, pk):
    from core.models import Timetable
    entry = get_object_or_404(Timetable, pk=pk)
    class_id = entry.class_assigned.id
    entry.delete()
    messages.success(request, "Timetable entry deleted successfully.")
    return redirect(f"{reverse('manage_timetable')}?class_id={class_id}")

@admin_required
def audit_log_list(request):
    """Filterable audit trail for system activity."""
    logs_query = AuditLog.objects.select_related('user').all()
    
    # Filtering
    action = request.GET.get('action')
    resource = request.GET.get('resource')
    if action:
        logs_query = logs_query.filter(action=action)
    if resource:
        logs_query = logs_query.filter(resource_type__icontains=resource)
        
    paginator = Paginator(logs_query, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'logs': page_obj,
        'actions': AuditLog.ACTION_CHOICES,
        'selected_action': action,
        'selected_resource': resource
    }
    return render(request, 'admin_dashboard/audit_logs.html', context)

@admin_required
def manage_terms(request):
    """Institutional Academic Term definition hub."""
    from core.models import AcademicTerm
    from .forms import AcademicTermForm
    
    terms = AcademicTerm.objects.all().order_by('-start_date')
    
    if request.method == 'POST':
        term_id = request.POST.get('term_id')
        if term_id:
            term = get_object_or_404(AcademicTerm, id=term_id)
            form = AcademicTermForm(request.POST, instance=term)
        else:
            form = AcademicTermForm(request.POST)
            
        if form.is_valid():
            form.save()
            messages.success(request, 'Academic Term synchronized successfully.')
            return redirect('manage_terms')
    else:
        form = AcademicTermForm()
        
    return render(request, 'admin_dashboard/terms.html', {
        'terms': terms,
        'form': form
    })

@admin_required
def delete_term(request, pk):
    from core.models import AcademicTerm
    term = get_object_or_404(AcademicTerm, pk=pk)
    if request.method == 'POST':
        term.delete()
        messages.warning(request, 'Term deleted permanently.')
    return redirect('manage_terms')


@admin_required
def manage_houses(request):
    houses = House.objects.all().order_by('-points')
    logs = HousePointLog.objects.select_related('house', 'awarded_by').all()[:20]
    
    if request.method == 'POST':
        if 'sync_protocol' in request.POST:
            count = StudentService.sync_all_unassigned_students()
            messages.success(request, f'Institutional Protocol Active: {count} student(s) successfully aligned with their Houses.')
            return redirect('manage_houses')
            
        house_id = request.POST.get('house_id')
        pts = int(request.POST.get('points', 0))
        category = request.POST.get('category', 'other')
        reason = request.POST.get('reason', 'Institutional Merit')
        
        house = get_object_or_404(House, id=house_id)
        
        HousePointLog.objects.create(
            house=house,
            points=pts,
            category=category,
            reason=reason,
            awarded_by=request.user
        )
        
        messages.success(request, f"Successfully adjusted points for {house.name} House!")
        return redirect('manage_houses')
        
    context = {
        'houses': houses,
        'logs': logs,
        'categories': HousePointLog.CATEGORIES,
    }
    return render(request, 'admin_dashboard/manage_houses.html', context)
