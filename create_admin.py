import os
import django
from django.core.management import ManagementUtility

def create_admin():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
    django.setup()
    
    from accounts.models import User
    
    username = os.environ.get('SUPERUSER_USERNAME', 'admin')
    email = os.environ.get('SUPERUSER_EMAIL', 'admin@example.com')
    password = os.environ.get('SUPERUSER_PASSWORD')
    
    if not password:
        print("SUPERUSER_PASSWORD not set. Skipping admin creation.")
        return

    if not User.objects.filter(username=username).exists():
        print(f"Creating superuser: {username}")
        User.objects.create_superuser(username=username, email=email, password=password)
    else:
        print(f"Superuser {username} already exists.")

if __name__ == "__main__":
    create_admin()
