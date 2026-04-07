from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from functools import wraps
from students.models import Student
from teachers.models import Teacher
from core.models import Class, Subject, Attendance, Result, Assignment, Submission
from .forms import StudentForm, TeacherForm, SubjectForm, ClassForm
from django.core.paginator import Paginator

from accounts.decorators import admin_required

from django.db.models import Count, Q, Avg
from analytics.views import _calculate_system_analytics, _calculate_performance_trend, _identify_at_risk_students

@admin_required
def admin_dashboard(request):
    system_analytics = _calculate_system_analytics()
    performance_trend = _calculate_performance_trend()
    at_risk_students = _identify_at_risk_students()
    
    total_students = system_analytics.get('total_students', 0)
    total_teachers = system_analytics.get('total_teachers', 0)
    total_classes = system_analytics.get('total_classes', 0)
    total_subjects = system_analytics.get('total_subjects', 0)
    
    attendance_stats = system_analytics.get('overall_attendance_rate', 0)
    
    students = Student.objects.with_performance_stats().select_related('user', 'class_enrolled').order_by('-user__date_joined')[:10]
    
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
def student_create(request):
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save()
            msg = f'Student {student.user.get_full_name()} created successfully.'
            if hasattr(form, 'generated_password'):
                msg += f' [User ID: {form.generated_username}] [Password: {form.generated_password}]'
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
            if hasattr(form, 'generated_password'):
                msg += f' [User ID: {form.generated_username}] [Password: {form.generated_password}]'
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
def delete_timetable_entry(request, pk):
    from core.models import Timetable
    entry = get_object_or_404(Timetable, pk=pk)
    class_id = entry.class_assigned.id
    if request.method == 'POST':
        entry.delete()
        messages.success(request, 'Timetable entry deleted successfully.')
    return redirect(f"{reverse('manage_timetable')}?class_id={class_id}")
