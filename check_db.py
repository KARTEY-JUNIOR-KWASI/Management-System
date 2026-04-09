import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from django.db import connection
from students.models import Student
from core.models import Class

print(f"--- DATABASE DIAGNOSTIC ---")
print(f"Engine: {settings.DATABASES['default']['ENGINE']}")
print(f"Name: {settings.DATABASES['default']['NAME']}")
print(f"Host: {settings.DATABASES['default'].get('HOST', 'Local/File')}")
print(f"Port: {settings.DATABASES['default'].get('PORT', 'Default')}")
print(f"---------------------------")
print(f"Students count: {Student.objects.count()}")
print(f"Classes count: {Class.objects.count()}")
print(f"---------------------------")
