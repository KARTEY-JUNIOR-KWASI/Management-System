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

    user_exists = User.objects.filter(username=username).first()
    if not user_exists:
        print(f"Creating superuser: {username}")
        User.objects.create_superuser(username=username, email=email, password=password, role='admin')
    else:
        print(f"Updating superuser: {username}")
        user_exists.set_password(password)
        user_exists.role = 'admin'
        user_exists.save()


if __name__ == "__main__":
    create_admin()
