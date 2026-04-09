import os
import django
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from students.models import Student
from admin_dashboard.views import _calculate_system_analytics, _calculate_performance_trend, _identify_at_risk_students

print("--- Testing with_performance_stats ---")
try:
    students = list(Student.objects.with_performance_stats()[:5])
    print(f"Success: {len(students)} students processed.")
except Exception as e:
    print(f"CRASH in with_performance_stats: {e}")
    import traceback
    traceback.print_exc()

print("\n--- Testing _calculate_system_analytics ---")
try:
    from analytics.views import _calculate_system_analytics
    stats = _calculate_system_analytics()
    print(f"Success: {stats.keys()}")
except Exception as e:
    print(f"CRASH in _calculate_system_analytics: {e}")
    import traceback
    traceback.print_exc()

print("\n--- Testing _identify_at_risk_students ---")
try:
    from analytics.views import _identify_at_risk_students
    at_risk = _identify_at_risk_students()
    print(f"Success: {len(at_risk)} at-risk students found.")
except Exception as e:
    print(f"CRASH in _identify_at_risk_students: {e}")
    import traceback
    traceback.print_exc()
