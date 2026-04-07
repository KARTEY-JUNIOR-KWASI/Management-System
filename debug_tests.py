import sys
import os
import django
import traceback
from django.test.utils import get_runner
from django.conf import settings

os.environ['DJANGO_SETTINGS_MODULE'] = 'school_management.settings'
django.setup()

def run_tests():
    try:
        TestRunner = get_runner(settings)
        test_runner = TestRunner(verbosity=2)
        # Run specific failing test to get detailed output
        failures = test_runner.run_tests(['admin_dashboard.tests.AdminDashboardTest.test_admin_dashboard_view'])
        if failures:
            print("\n" + "="*50)
            print("TEST FAILED - see traceback above")
            print("="*50 + "\n")
        sys.exit(bool(failures))
    except Exception:
        print("\n" + "!"*50)
        print("EXCEPTION DURING TEST RUN:")
        traceback.print_exc()
        print("!"*50 + "\n")
        sys.exit(1)

if __name__ == '__main__':
    run_tests()
