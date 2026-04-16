from django.http import JsonResponse
from django.db.models import Q, Sum, Avg
from students.models import Student
from teachers.models import Teacher
from core.models import Class, Attendance, House
from finance.models import Invoice, Payment
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth.decorators import login_required

@login_required
def global_search(request):
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return JsonResponse({'results': []})

    results = []

    # Search Students
    students = Student.objects.filter(
        Q(user__first_name__icontains=query) |
        Q(user__last_name__icontains=query) |
        Q(student_id__icontains=query)
    ).select_related('user', 'class_enrolled')[:5]

    for s in students:
        results.append({
            'type': 'Student',
            'label': f"{s.user.get_full_name()} ({s.student_id})",
            'sub': s.class_enrolled.name if s.class_enrolled else "No Class",
            'url': f"/admin-dashboard/students/{s.id}/",
            'icon': 'graduation-cap'
        })

    # Search Teachers
    teachers = Teacher.objects.filter(
        Q(user__first_name__icontains=query) |
        Q(user__last_name__icontains=query)
    ).select_related('user')[:5]

    for t in teachers:
        results.append({
            'type': 'Faculty',
            'label': t.user.get_full_name(),
            'sub': "Active Faculty",
            'url': f"/admin-dashboard/teachers/{t.id}/",
            'icon': 'briefcase'
        })

    # Search Classes
    classes = Class.objects.filter(Q(name__icontains=query))[:5]
    for c in classes:
        results.append({
            'type': 'Sector',
            'label': f"Class {c.name}",
            'sub': "Academic Unit",
            'url': f"/admin-dashboard/classes/{c.id}/",
            'icon': 'layers'
        })

    # Action Shortcuts (for Admin)
    if request.user.role == 'admin':
        shortcuts = [
            {'q': 'finance', 'label': 'Finance Hub', 'url': '/finance/', 'icon': 'wallet'},
            {'q': 'house', 'label': 'House Alliances', 'url': '/admin-dashboard/settings/houses/', 'icon': 'shield'},
            {'q': 'library', 'label': 'Library Vault', 'url': '/library/', 'icon': 'library-big'},
            {'q': 'settings', 'label': 'System Settings', 'url': '/admin-dashboard/settings/', 'icon': 'settings'}
        ]
        for s in shortcuts:
            if query.lower() in s['q']:
                results.append({
                    'type': 'System Action',
                    'label': s['label'],
                    'sub': 'Module Shortcut',
                    'url': s['url'],
                    'icon': s['icon']
                })

    return JsonResponse({'results': results})

@login_required
def pulse_diagnostics(request):
    # Today's Attendance Pulse
    today = timezone.now().date()
    total_students = Student.objects.count()
    present_today = Attendance.objects.filter(date=today, status='present').count()
    
    attendance_pulse = (present_today / total_students * 100) if total_students > 0 else 0

    # Revenue Velocity
    total_expected = Invoice.objects.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    total_collected = Payment.objects.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
    revenue_pulse = (total_collected / total_expected * 100) if total_expected > 0 else 0

    return JsonResponse({
        'attendance_pulse': round(attendance_pulse, 1),
        'revenue_pulse': round(revenue_pulse, 1),
        'status': 'Synchronized' if attendance_pulse > 70 else 'Diagnostic Required'
    })
