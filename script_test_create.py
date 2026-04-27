import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()
from django.test import Client
from django.urls import reverse
from accounts.models import User

c = Client()
admin = User.objects.filter(role='admin').first()

if not admin:
    print("Error: No admin user found. Please run seed_data or create_admin first.")
else:
    c.force_login(admin)
    url = reverse('student_create')
    print(f"--- Testing Create Page (GET) at {url} ---")
    response = c.get(url)
    print('Create Page GET:', response.status_code)
    
    if response.status_code != 200:
        print("WARNING: Create page returned non-200 status code.")

