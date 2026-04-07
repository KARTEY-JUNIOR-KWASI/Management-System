from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.forms import modelformset_factory
from django.http import HttpResponse
from django.db.models import Count, Q
from core.models import Attendance, Class, Subject, Result, Assignment, Submission
from students.models import Student
from .models import Teacher
from .forms import AttendanceDateForm, AttendanceFormSet, GradeSelectionForm, BulkGradeForm, AssignmentForm
from datetime import date
from school_management.sms_service import send_attendance_sms, send_absence_sms
from analytics.views import _calculate_class_performance, _identify_at_risk_students, _calculate_assignment_stats
from collections import defaultdict

from accounts.decorators import teacher_required


def _get_or_create_teacher(user):
    teacher, created = Teacher.objects.get_or_create(
        user=user,
        defaults={
            'teacher_id': f'TCHR{user.id:05d}',
        }
    )
    return teacher


def _get_teacher_classes(user):
    """
    Returns all classes a teacher is associated with:
    - Classes where they are the designated class_teacher, OR
    - Classes that have students who study their subjects (via the Subject model)
    This makes the system robust even if class_teacher isn't formally assigned.
    """
    teacher = _get_or_create_teacher(user)
    teacher_subjects = teacher.subjects.all()

    # Classes where this teacher is the class teacher
    direct_classes = Class.objects.filter(class_teacher=user)

    # Also any class that has been explicitly assigned in assignments by this teacher
    assignment_classes = Class.objects.filter(assignments__teacher=user).distinct()

    # Combine and deduplicate
    all_class_ids = set(
        list(direct_classes.values_list('id', flat=True)) +
        list(assignment_classes.values_list('id', flat=True))
    )

    if all_class_ids:
        return Class.objects.filter(id__in=all_class_ids)

    # Fallback: if teacher has subjects, return ALL classes so they can at least function
    if teacher_subjects.exists():
        return Class.objects.all()

    return Class.objects.none()


@teacher_required
def teacher_dashboard(request):
    from analytics.views import _calculate_class_performance, _identify_at_risk_students, _calculate_assignment_stats
    
    teacher = _get_or_create_teacher(request.user)
    classes = _get_teacher_classes(request.user)
    recent_assignments = Assignment.objects.filter(teacher=request.user).order_by('-created_at')[:5]

    # Analytics Data
    class_performance = _calculate_class_performance(teacher)
    at_risk_students = _identify_at_risk_students()
    # Filter at-risk students to only those in THIS teacher's classes
    teacher_class_ids = set(classes.values_list('id', flat=True))
    my_at_risk = [s for s in at_risk_students if s['student'].class_enrolled and s['student'].class_enrolled.id in teacher_class_ids]
    
    assignment_stats = _calculate_assignment_stats(teacher)

    context = {
        'teacher': teacher,
        'classes': classes,
        'recent_assignments': recent_assignments,
        'total_students': Student.objects.filter(class_enrolled__in=classes).count(),
        'total_classes': classes.count(),
        'class_performance': class_performance,
        'at_risk_students': my_at_risk[:5],
        'total_at_risk': len(my_at_risk),
        'assignment_stats': assignment_stats,
    }
    return render(request, 'teachers/dashboard.html', context)


@teacher_required
def mark_attendance(request):
    teacher = _get_or_create_teacher(request.user)
    teacher_classes = _get_teacher_classes(request.user)

    selected_class = None
    selected_date = None
    students = []
    attendance_records = {}

    if request.method == 'POST':
        if 'load_class' in request.POST:
            class_id = request.POST.get('class_id')
            selected_date = request.POST.get('date')
            selected_class = get_object_or_404(Class, id=class_id)
            students = Student.objects.filter(class_enrolled=selected_class).select_related('user')

            # Load or initialize attendance for each student
            for student in students:
                att, _ = Attendance.objects.get_or_create(
                    student=student,
                    class_attended=selected_class,
                    date=selected_date,
                    defaults={'status': 'present', 'marked_by': request.user}
                )
                attendance_records[student.id] = att

        elif 'save_attendance' in request.POST:
            class_id = request.POST.get('class_id')
            selected_date = request.POST.get('date')
            selected_class = get_object_or_404(Class, id=class_id)
            students = Student.objects.filter(class_enrolled=selected_class).select_related('user')

            sms_sent = 0
            for student in students:
                status = request.POST.get(f'status_{student.id}', 'absent')
                Attendance.objects.update_or_create(
                    student=student,
                    class_attended=selected_class,
                    date=selected_date,
                    defaults={'status': status, 'marked_by': request.user}
                )
                # 📱 SMS Hook: notify when student is marked as absent (Critical) or present (Routine)
                if status == 'absent':
                    sent = send_absence_sms(student)
                    if sent:
                        sms_sent += 1
                elif status == 'present':
                    # Optional: present notification (currently enabled as per previous logic)
                    send_attendance_sms(student)
                    # We only count absolute alerts in the success message for now
                    if status == 'absent': sms_sent += 1

            sms_note = f" {sms_sent} URGENT absence alert(s) sent to parents." if sms_sent > 0 else ""
            messages.success(request, f'Attendance saved for {selected_class} on {selected_date}!{sms_note}')
            return redirect('mark_attendance')

    context = {
        'teacher_classes': teacher_classes,
        'selected_class': selected_class,
        'selected_date': selected_date,
        'students': students,
        'attendance_records': attendance_records,
        'today': date.today().isoformat(),
    }
    return render(request, 'teachers/mark_attendance.html', context)


@teacher_required
def attendance_report(request):
    teacher = _get_or_create_teacher(request.user)
    teacher_classes = _get_teacher_classes(request.user)

    selected_class = None
    attendance_data = []
    total_present = 0
    total_absent = 0
    total_late = 0

    class_id = request.GET.get('class_id')
    if class_id:
        selected_class = get_object_or_404(Class, id=class_id)
        students = Student.objects.filter(class_enrolled=selected_class).select_related('user')

        # Bulk aggregate attendance for all students in the class
        attendance_stats = Attendance.objects.filter(
            student__in=students, class_attended=selected_class
        ).values('student_id').annotate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present')),
            absent=Count('id', filter=Q(status='absent')),
            late=Count('id', filter=Q(status='late'))
        )
        stats_map = {s['student_id']: s for s in attendance_stats}

        # Pre-fetch recent records to avoid N+1 in the loop
        recent_records = Attendance.objects.filter(
            student__in=students, class_attended=selected_class
        ).order_by('-date')
        records_map = defaultdict(list)
        for r in recent_records:
            if len(records_map[r.student_id]) < 10:
                records_map[r.student_id].append(r)

        for student in students:
            stat = stats_map.get(student.id, {'total': 0, 'present': 0, 'absent': 0, 'late': 0})
            total = stat['total']
            present = stat['present']
            absent = stat['absent']
            late = stat['late']
            percentage = round((present / total * 100), 1) if total > 0 else 0

            total_present += present
            total_absent += absent
            total_late += late

            attendance_data.append({
                'student': student,
                'total': total,
                'present': present,
                'absent': absent,
                'late': late,
                'percentage': percentage,
                'records': records_map[student.id],
            })

    context = {
        'teacher_classes': teacher_classes,
        'selected_class': selected_class,
        'attendance_data': attendance_data,
        'total_present': total_present,
        'total_absent': total_absent,
        'total_late': total_late,
    }
    return render(request, 'teachers/attendance_report.html', context)


@teacher_required
def manage_grades(request):
    teacher = _get_or_create_teacher(request.user)
    teacher_classes = _get_teacher_classes(request.user)
    teacher_subjects = teacher.subjects.all()

    selected_class = None
    selected_subject = None
    students = []

    if request.method == 'POST':
        if 'save_grades' in request.POST:
            class_id = request.POST.get('class_id')
            subject_id = request.POST.get('subject_id')
            exam_type = request.POST.get('exam_type')
            max_score = request.POST.get('max_score', 100)

            selected_class = get_object_or_404(Class, id=class_id)
            selected_subject = get_object_or_404(Subject, id=subject_id)
            students = Student.objects.filter(class_enrolled=selected_class).select_related('user')

            saved = 0
            for student in students:
                score_key = f'score_{student.id}'
                score = request.POST.get(score_key)
                if score and score.strip():
                    try:
                        score_val = float(score)
                        Result.objects.update_or_create(
                            student=student,
                            subject=selected_subject,
                            exam_type=exam_type,
                            defaults={
                                'score': score_val,
                                'max_score': float(max_score),
                                'teacher': request.user,
                            }
                        )
                        saved += 1
                    except ValueError:
                        pass

            messages.success(request, f'Grades saved for {saved} student(s) in {selected_subject} — {exam_type}!')
            return redirect('manage_grades')

    # Load class/subject from GET for display
    class_id = request.GET.get('class_id')
    subject_id = request.GET.get('subject_id')
    if class_id and subject_id:
        selected_class = get_object_or_404(Class, id=class_id)
        selected_subject = get_object_or_404(Subject, id=subject_id)
        students = Student.objects.filter(class_enrolled=selected_class).select_related('user')

        # Pre-fill existing grades optimally
        results = Result.objects.filter(student__in=students, subject=selected_subject)
        results_by_student = defaultdict(dict)
        for r in results:
            results_by_student[r.student_id][r.exam_type] = r
            
        for student in students:
            student.existing_grades = results_by_student.get(student.id, {})

    exam_types = [('midterm', 'Midterm'), ('final', 'Final'), ('quiz', 'Quiz'), ('assignment', 'Assignment')]

    context = {
        'teacher_classes': teacher_classes,
        'teacher_subjects': teacher_subjects,
        'selected_class': selected_class,
        'selected_subject': selected_subject,
        'students': students,
        'exam_types': exam_types,
    }
    return render(request, 'teachers/manage_grades.html', context)


@teacher_required
def grade_report(request):
    teacher = _get_or_create_teacher(request.user)
    teacher_classes = _get_teacher_classes(request.user)
    teacher_subjects = teacher.subjects.all()

    selected_class = None
    selected_subject = None
    grade_data = []

    class_id = request.GET.get('class_id')
    subject_id = request.GET.get('subject_id')

    if class_id:
        selected_class = get_object_or_404(Class, id=class_id)
        students = Student.objects.filter(class_enrolled=selected_class).select_related('user')

        results_qs = Result.objects.filter(student__in=students)
        if subject_id:
            selected_subject = get_object_or_404(Subject, id=subject_id)
            results_qs = results_qs.filter(subject=selected_subject)

        # Pre-fetch all results for students in this class to avoid O(N) queries
        results_by_student = defaultdict(list)
        for r in results_qs.select_related('subject'):
            results_by_student[r.student_id].append(r)

        for student in students:
            s_results = results_by_student[student.id]
            total = len(s_results)
            if total > 0:
                avg = sum((r.score / r.max_score * 100) for r in s_results) / total
            else:
                avg = 0

            grade_letter = 'F'
            if avg >= 90: grade_letter = 'A'
            elif avg >= 80: grade_letter = 'B'
            elif avg >= 70: grade_letter = 'C'
            elif avg >= 60: grade_letter = 'D'

            grade_data.append({
                'student': student,
                'results': s_results,
                'average': round(avg, 1),
                'grade_letter': grade_letter,
            })

    context = {
        'teacher_classes': teacher_classes,
        'teacher_subjects': teacher_subjects,
        'selected_class': selected_class,
        'selected_subject': selected_subject,
        'grade_data': grade_data,
    }
    return render(request, 'teachers/grade_report.html', context)


@teacher_required
def create_assignment(request):
    teacher = _get_or_create_teacher(request.user)
    teacher_classes = _get_teacher_classes(request.user)
    teacher_subjects = teacher.subjects.all()

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        subject_id = request.POST.get('subject_id')
        class_id = request.POST.get('class_id')
        due_date = request.POST.get('due_date')
        uploaded_file = request.FILES.get('file')

        errors = []
        if not title: errors.append('Title is required.')
        if not description: errors.append('Description is required.')
        if not subject_id: errors.append('Please select a subject.')
        if not class_id: errors.append('Please select a class.')
        if not due_date: errors.append('Due date is required.')

        if not errors:
            subject = get_object_or_404(Subject, id=subject_id)
            cls = get_object_or_404(Class, id=class_id)

            assignment = Assignment.objects.create(
                title=title,
                description=description,
                subject=subject,
                class_assigned=cls,
                teacher=request.user,
                due_date=due_date,
                file=uploaded_file,
            )
            messages.success(request, f'Assignment "{title}" created successfully!')
            return redirect('manage_assignments')
        else:
            for err in errors:
                messages.error(request, err)

    context = {
        'teacher_classes': teacher_classes,
        'teacher_subjects': teacher_subjects,
    }
    return render(request, 'teachers/create_assignment.html', context)


@teacher_required
def manage_assignments(request):
    teacher = _get_or_create_teacher(request.user)
    # Use annotation to get counts in one query instead of looping (fixes N+1)
    assignments = Assignment.objects.filter(teacher=request.user).select_related(
        'subject', 'class_assigned'
    ).annotate(
        submission_count=Count('submission', distinct=True),
        graded_count=Count('submission', filter=Q(submission__grade__isnull=False), distinct=True)
    ).order_by('-created_at')

    context = {
        'assignments': assignments,
        'today': date.today(),
    }
    return render(request, 'teachers/manage_assignments.html', context)


@teacher_required
def grade_submissions(request, assignment_id):
    teacher = _get_or_create_teacher(request.user)
    assignment = get_object_or_404(Assignment, id=assignment_id, teacher=request.user)
    
    # Get all students in the class
    class_students = Student.objects.filter(class_enrolled=assignment.class_assigned).select_related('user')
    
    # Get existings submissions
    submissions_query = Submission.objects.filter(assignment=assignment)
    submission_dict = {sub.student_id: sub for sub in submissions_query}
    
    # Build unified roster
    roster = []
    for student in class_students:
        sub = submission_dict.get(student.id)
        roster.append({
            'student': student,
            'submission': sub,
            'has_submitted': sub is not None,
            'grade': sub.grade if sub else None,
            'feedback': sub.feedback if sub else '',
        })

    if request.method == 'POST':
        # Batch Grading Logic
        student_ids = request.POST.getlist('student_ids')
        for sid in student_ids:
            grade = request.POST.get(f'grade_{sid}')
            feedback = request.POST.get(f'feedback_{sid}', '')
            
            if grade:
                try:
                    student = Student.objects.get(id=sid)
                    # Find or create submission for grading
                    submission, created = Submission.objects.get_or_create(
                        assignment=assignment,
                        student=student,
                        defaults={'feedback': feedback}
                    )
                    submission.grade = grade
                    submission.feedback = feedback
                    submission.save()
                except Student.DoesNotExist:
                    continue
        
        messages.success(request, f'Successfully updated grades for the roster.')
        return redirect('grade_submissions', assignment_id=assignment.id)

    context = {
        'assignment': assignment,
        'roster': roster,
        'total_students': len(roster),
        'total_submitted': len(submission_dict),
    }
    return render(request, 'teachers/grade_submissions.html', context)


@teacher_required
def student_report_card(request, student_id):
    """Generate a printable report card for a student."""
    teacher = _get_or_create_teacher(request.user)
    teacher_classes = _get_teacher_classes(request.user)

    student = get_object_or_404(Student, id=student_id, class_enrolled__in=teacher_classes)

    results = Result.objects.filter(student=student).select_related('subject').order_by('subject__name', 'exam_type')

    # Group results by subject
    subject_results = {}
    for r in results:
        subj_name = r.subject.name
        if subj_name not in subject_results:
            subject_results[subj_name] = {'results': [], 'average': 0}
        pct = (r.score / r.max_score * 100) if r.max_score else 0
        subject_results[subj_name]['results'].append({
            'exam_type': r.get_exam_type_display() if hasattr(r, 'get_exam_type_display') else r.exam_type,
            'score': r.score,
            'max_score': r.max_score,
            'percentage': round(pct, 1),
        })

    # Compute per-subject average
    for subj, data in subject_results.items():
        if data['results']:
            data['average'] = round(sum(r['percentage'] for r in data['results']) / len(data['results']), 1)

    # Overall average
    all_pcts = [r['percentage'] for s in subject_results.values() for r in s['results']]
    overall_avg = round(sum(all_pcts) / len(all_pcts), 1) if all_pcts else 0

    overall_grade = 'F'
    if overall_avg >= 90: overall_grade = 'A'
    elif overall_avg >= 80: overall_grade = 'B'
    elif overall_avg >= 70: overall_grade = 'C'
    elif overall_avg >= 60: overall_grade = 'D'

    # Attendance
    att_records = Attendance.objects.filter(student=student)
    att_total = att_records.count()
    att_present = att_records.filter(status='present').count()
    att_pct = round((att_present / att_total * 100), 1) if att_total > 0 else 0

    context = {
        'student': student,
        'subject_results': subject_results,
        'overall_avg': overall_avg,
        'overall_grade': overall_grade,
        'att_total': att_total,
        'att_present': att_present,
        'att_pct': att_pct,
        'teacher': teacher,
    }
    return render(request, 'teachers/report_card.html', context)

@teacher_required
def teacher_timetable(request):
    from core.models import Timetable
    teacher = request.user
    
    # Get all timetable entries assigned to this teacher
    timetables = Timetable.objects.filter(teacher=teacher).select_related('class_assigned', 'subject').order_by('start_time')

    DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']

    # Group timetables by day for display
    schedule_dict = {day: [] for day in DAYS}
    for t in timetables:
        if t.day in schedule_dict:
            schedule_dict[t.day].append(t)
            
    schedule_list = [(day.capitalize(), schedule_dict[day]) for day in DAYS]

    context = {
        'schedule_list': schedule_list,
    }
    return render(request, 'teachers/timetable.html', context)
