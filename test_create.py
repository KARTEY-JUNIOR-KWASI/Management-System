import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()
from django.test import Client
from accounts.models import User
c = Client()
admin = User.objects.filter(role='admin').first()
c.force_login(admin)
response = c.get('/admin-dashboard/students/create/')
print('Create Page GET:', response.status_code)
