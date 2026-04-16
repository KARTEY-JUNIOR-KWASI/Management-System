from django.db import models
from django.contrib.auth.models import AbstractUser

class Badge(models.Model):
    """Gamified achievement badge for students and teachers."""
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon_class = models.CharField(max_length=50, help_text="FontAwesome class (e.g., fa-star)")
    color_hex = models.CharField(max_length=7, default="#004067")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
        ('parent', 'Parent'),
    )
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    has_completed_onboarding = models.BooleanField(default=False)
    
    # Achievements
    badges = models.ManyToManyField(Badge, related_name='users', blank=True)

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"
