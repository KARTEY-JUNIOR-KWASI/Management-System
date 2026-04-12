import os
import django
from django.test import Client
from django.urls import reverse

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from accounts.models import User

def debug_login():
    c = Client()
    # Try logging in as the student
    username = 'karteyjunior'
    password = 'password' # Assuming standard test password
    
    print(f"--- Debugging login for {username} ---")
    
    # Check if user exists
    try:
        user = User.objects.get(username=username)
        print(f"User found: {user.username}, Role: {user.role}, Is Active: {user.is_active}")
    except User.DoesNotExist:
        print("User not found!")
        return

    # Simulate login
    # Since we use allauth, let's try to get the login page first
    login_url = reverse('account_login')
    response = c.get(login_url)
    print(f"Login Page Status: {response.status_code}")
    
    # Actually log in
    # This might fail if the password isn't 'password', 
    # but we can force login for testing the decorators
    c.force_login(user)
    print("Force logged in.")
    
    # Try to access student dashboard
    dash_url = reverse('student_dashboard')
    response = c.get(dash_url)
    print(f"Student Dashboard Status: {response.status_code}")
    if response.status_code == 403:
        print("Forbidden detected!")
        # Print a bit of the content if it's a 403
        print(response.content[:500].decode())
        
    # Try to access student finance hub
    finance_url = reverse('finance:student_finance_hub')
    response = c.get(finance_url)
    print(f"Student Finance Hub Status: {response.status_code}")
    if response.status_code == 403:
        print("Forbidden on Finance Hub detected!")

if __name__ == "__main__":
    debug_login()
