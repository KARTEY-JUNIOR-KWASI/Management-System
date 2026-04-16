import os
import django

# Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from core.models import House

def initialize_houses():
    houses_data = [
        {'name': 'Red', 'color_code': '#ef4444', 'motto': 'Strength Through Unity, Victory Through Courage.'},
        {'name': 'Blue', 'color_code': '#3b82f6', 'motto': 'Wisdom to Lead, Intelligence to Prevail.'},
        {'name': 'Yellow', 'color_code': '#eab308', 'motto': 'Excellence in Action, Brilliance in Mind.'},
        {'name': 'Green', 'color_code': '#22c55e', 'motto': 'Growth in Knowledge, Harmony in Spirit.'},
    ]

    print("🛡️ Initializing Institutional Alliances...")
    for data in houses_data:
        house, created = House.objects.get_or_create(
            name=data['name'],
            defaults={
                'color_code': data['color_code'],
                'motto': data['motto'],
                'points': 100, # Start with base points
                'patron': 'Institutional Board'
            }
        )
        if created:
            print(f"✅ Created Alliance: {house.name} House")
        else:
            # Update values if they exist
            house.color_code = data['color_code']
            house.motto = data['motto']
            house.save()
            print(f"🔄 Updated Alliance: {house.name} House")

if __name__ == '__main__':
    initialize_houses()
