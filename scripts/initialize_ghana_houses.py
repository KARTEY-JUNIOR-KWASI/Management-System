import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from core.models import House

def initialize_houses():
    houses_data = [
        {'name': 'House 1', 'color_code': '#ef4444', 'description': 'The Red House - Valor and Strength'},
        {'name': 'House 2', 'color_code': '#3b82f6', 'description': 'The Blue House - Loyalty and Wisdom'},
        {'name': 'House 3', 'color_code': '#eab308', 'description': 'The Yellow House - Joy and Energy'},
        {'name': 'House 4', 'color_code': '#22c55e', 'description': 'The Green House - Growth and Harmony'},
    ]

    print("Initializing Ghana Institutional House System...")
    for data in houses_data:
        house, created = House.objects.get_or_create(
            name=data['name'],
            defaults={
                'color_code': data['color_code'],
                'description': data['description']
            }
        )
        if created:
            print(f"Created: {house.name} ({house.color_code})")
        else:
            # Update colors if they already exist but have different colors
            house.color_code = data['color_code']
            house.description = data['description']
            house.save()
            print(f"Updated: {house.name} ({house.color_code})")

    print("\nHouse initialization complete.")

if __name__ == "__main__":
    initialize_houses()
