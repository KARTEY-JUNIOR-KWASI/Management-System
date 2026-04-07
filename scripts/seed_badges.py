import os
import sys
import django

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from accounts.models import Badge

def seed_badges():
    badges = [
        {
            "name": "Academic Pioneer",
            "description": "Awarded for being among the first to complete the modernized onboarding.",
            "icon_class": "fa-rocket",
            "color_hex": "#6366f1"
        },
        {
            "name": "Knowledge Anchor",
            "description": "Awarded for uploading over 5 standard-compliant resources to the library.",
            "icon_class": "fa-anchor",
            "color_hex": "#0ea5e9"
        },
        {
            "name": "Master Grader",
            "description": "Awarded to educators who utilize the Batch Grading tool for efficient throughput.",
            "icon_class": "fa-bolt",
            "color_hex": "#f59e0b"
        },
        {
            "name": "Mastery Achiever",
            "description": "Awarded to students with a GPA exceeding 3.8 in the current term.",
            "icon_class": "fa-medal",
            "color_hex": "#10b981"
        },
        {
            "name": "Intelligence Seeker",
            "description": "Awarded for viewing more than 20 unique library resources.",
            "icon_class": "fa-brain",
            "color_hex": "#8b5cf6"
        },
        {
            "name": "Perfect Presence",
            "description": "Awarded for 100% attendance over a 30-day institutional window.",
            "icon_class": "fa-calendar-check",
            "color_hex": "#ec4899"
        }
    ]

    for b_data in badges:
        badge, created = Badge.objects.get_or_create(
            name=b_data["name"],
            defaults={
                "description": b_data["description"],
                "icon_class": b_data["icon_class"],
                "color_hex": b_data["color_hex"]
            }
        )
        if created:
            print(f"Created badge: {badge.name}")
        else:
            print(f"Badge already exists: {badge.name}")

if __name__ == "__main__":
    seed_badges()
