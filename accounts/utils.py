import random
import string
from django.utils import timezone
from .models import User

def generate_user_id(role):
    """
    Generates a unique User ID in the format: EDU-{ROLE}-{YEAR}-{SEQUENCE}
    Example: EDU-STU-24-001
    """
    year = timezone.now().strftime('%y')
    role_code = "STU" if role == 'student' else "TEA" if role == 'teacher' else "ADM"
    
    prefix = f"EDU-{role_code}-{year}-"
    
    # Get the latest ID for this role/year
    last_user = User.objects.filter(username__startswith=prefix).order_by('username').last()
    
    if last_user:
        try:
            last_seq = int(last_user.username.split('-')[-1])
            new_seq = last_seq + 1
        except (ValueError, IndexError):
            new_seq = 1
    else:
        new_seq = 1
        
    return f"{prefix}{new_seq:03d}"

def generate_random_password(length=10):
    """Generates a secure random password."""
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(characters) for i in range(length))
