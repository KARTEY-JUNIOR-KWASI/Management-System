from django.db.models import Avg, Sum, Count, Q
from core.models import Result, Student

def calculate_student_averages(student_ids=None, class_id=None):
    """
    Calculates weighted averages and total scores for a set of students.
    Returns a dictionary of results indexed by student_id.
    """
    query = Result.objects.all()
    if class_id:
        query = query.filter(student__class_enrolled_id=class_id)
    if student_ids:
        query = query.filter(student_id__in=student_ids)

    # Aggregate performance per student
    performance = query.values('student').annotate(
        total_score=Sum('score'),
        total_max=Sum('max_score'),
        exam_count=Count('id')
    )

    results = {}
    for p in performance:
        percentage = (p['total_score'] / p['total_max'] * 100) if p['total_max'] > 0 else 0
        results[p['student']] = {
            'total_score': float(p['total_score']),
            'percentage': float(percentage),
            'exam_count': p['exam_count']
        }
    return results

def get_class_rankings(class_id):
    """
    Computes absolute student positions (ranks) for a specific class.
    Handles tie-breakers by assigning same rank to identical scores.
    """
    from students.models import Student
    
    students = Student.objects.filter(class_enrolled_id=class_id).select_related('user')
    performance_map = calculate_student_averages(class_id=class_id)
    
    ranked_list = []
    for student in students:
        perf = performance_map.get(student.id, {'total_score': 0, 'percentage': 0, 'exam_count': 0})
        ranked_list.append({
            'student': student,
            'avg_percentage': perf['percentage'],
            'total_score': perf['total_score'],
            'exam_count': perf['exam_count']
        })
    
    # Sort by percentage descending
    ranked_list.sort(key=lambda x: x['avg_percentage'], reverse=True)
    
    # Assign positions
    current_rank = 0
    last_percentage = -1
    for i, item in enumerate(ranked_list):
        if item['avg_percentage'] != last_percentage:
            current_rank = i + 1
        item['position'] = current_rank
        last_percentage = item['avg_percentage']
        
    return ranked_list

def get_ordinal(n):
    """Convert integer to ordinal string (1st, 2nd, etc.)"""
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
    return str(n) + suffix
