from django.db.models import Avg, Count, Q
from core.models import Result, Subject, Attendance, Assignment, Submission
from datetime import date, timedelta

def _calculate_student_performance(student):
    """
    Stand-alone calculation of detailed performance metrics for a student.
    Logic moved here to prevent view-level circular dependencies.
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
    subject_performance = []
    # Identify subjects student has assignments for
    subject_ids = Assignment.objects.filter(class_assigned=student.class_enrolled).values_list('subject_id', flat=True).distinct()
    subjects = Subject.objects.filter(id__in=subject_ids)
    
    for subject in subjects:
        subject_results = [r for r in results if r.subject_id == subject.id]
        if subject_results:
            subject_avg = sum(r.score for r in subject_results) / len(subject_results)
            subject_performance.append({
                'subject': {
                    'id': subject.id,
                    'name': subject.name
                },
                'average_score': float(subject_avg),
                'grade_points': float(min(4.0, subject_avg / 25)),
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
    """
    Generate grade predictions based on current performance stats.
    """
    performance = _calculate_student_performance(student)
    predictions = []
    
    for subject_data in performance['subject_performance']:
        current_avg = subject_data['average_score']
        
        # Simple prediction model: assume 5% improvement if attendance is > 90%
        # or 2% decline if attendance is < 70%
        attendance_impact = 0
        if performance['attendance_rate'] > 90:
            attendance_impact = 5
        elif performance['attendance_rate'] < 70:
            attendance_impact = -3
            
        predicted = min(100, max(0, current_avg + attendance_impact))
        
        predictions.append({
            'subject': subject_data['subject']['name'], # Return name for flat dict
            'subject_obj': subject_data['subject'],
            'current_average': current_avg,
            'predicted_score': predicted,
            'confidence': 0.85 if performance['attendance_rate'] > 80 else 0.65
        })
        
    return predictions
