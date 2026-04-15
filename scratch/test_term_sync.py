import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from core.models import AcademicTerm, SchoolConfiguration
from datetime import date

def verify_sync():
    print("🚀 Initializing institutional sync test...")
    
    # Create a test term
    test_term = AcademicTerm(
        name="Test Term 2026",
        session="2025/2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 4, 1),
        is_current=True
    )
    test_term.save()
    print(f"✅ Created current term: {test_term}")
    
    # Check singleton
    config = SchoolConfiguration.get_config()
    print(f"📡 Current School Config Active Term: {config.active_term}")
    
    if config.active_term and config.active_term.id == test_term.id:
        print("🏆 SUCCESS: Sync protocol verified. SchoolConfiguration matched new term.")
    else:
        print("❌ FAILURE: Sync protocol failed. SchoolConfiguration did not update.")

if __name__ == "__main__":
    verify_sync()
