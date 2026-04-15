import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()
from django.test.client import Client
from accounts.models import User

c = Client()
u = User.objects.filter(role='student').first()
c.force_login(u)
response = c.get('/library/student/')
with open('scratch/rendered_library.html', 'wb') as f:
    f.write(response.content)
print("Rendered to scratch/rendered_library.html")
