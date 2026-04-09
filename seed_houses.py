import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from core.models import House

def seed_houses():
    houses = [
        {'name': 'House 1', 'color_code': '#dc3545', 'description': 'The Red House - Valor and Courage'},
        {'name': 'House 2', 'color_code': '#0d6efd', 'description': 'The Blue House - Wisdom and Vision'},
        {'name': 'House 3', 'color_code': '#198754', 'description': 'The Green House - Growth and Prosperity'},
        {'name': 'House 4', 'color_code': '#ffc107', 'description': 'The Yellow House - Brilliance and Joy'},
    ]

    for h_data in houses:
        house, created = House.objects.get_or_create(
            name=h_data['name'],
            defaults={'color_code': h_data['color_code'], 'description': h_data['description']}
        )
        if created:
            print(f"Created {house.name}")
        else:
            print(f"{house.name} already exists")

if __name__ == "__main__":
    seed_houses()
