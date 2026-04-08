from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from .models import AuditLog, SchoolConfiguration, Class, Subject, Result
from students.models import Student
from teachers.models import Teacher
from .middleware import get_current_user, get_current_ip
from .utils import NotificationService

def log_action(user, action, resource_type, resource_id, description):
    # Ensure AnonymousUser is not assigned to the ForeignKey
    final_user = user if user and user.is_authenticated else None
    
    AuditLog.objects.create(
        user=final_user,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        description=description,
        ip_address=get_current_ip()
    )

# Auth Signals
@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    log_action(user, 'LOGIN', 'User', user.id, f"User {user.username} logged in.")

@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    if user:
        log_action(user, 'LOGOUT', 'User', user.id, f"User {user.username} logged out.")

@receiver(user_login_failed)
def log_login_failed(sender, credentials, request, **kwargs):
    log_action(None, 'SECURITY', 'Auth', None, f"Failed login attempt for username: {credentials.get('username')}")

# Model Signals
@receiver(post_save, sender=Student)
@receiver(post_save, sender=Teacher)
@receiver(post_save, sender=Result)
@receiver(post_save, sender=Class)
@receiver(post_save, sender=Subject)
@receiver(post_save, sender=SchoolConfiguration)
def log_post_save(sender, instance, created, **kwargs):
    user = get_current_user()
    action = 'CREATE' if created else 'UPDATE'
    resource_type = sender.__name__
    resource_id = instance.id
    
    # Custom descriptions
    if resource_type == 'Student':
        desc = f"{action} student: {instance.user.get_full_name()} ({instance.student_id})"
    elif resource_type == 'Teacher':
        desc = f"{action} teacher: {instance.user.get_full_name()}"
    elif resource_type == 'SchoolConfiguration':
        desc = f"Institutional configuration {action.lower()}d."
        action = 'SYSTEM'
    else:
        desc = f"{action} {resource_type.lower()}: {str(instance)}"

    log_action(user, action, resource_type, resource_id, desc)

    # Automated Alerts
    if resource_type == 'Result' and created:
        NotificationService.notify_result_published(instance)

@receiver(post_delete, sender=Student)
@receiver(post_delete, sender=Teacher)
@receiver(post_delete, sender=Result)
@receiver(post_delete, sender=Class)
@receiver(post_delete, sender=Subject)
def log_post_delete(sender, instance, **kwargs):
    user = get_current_user()
    resource_type = sender.__name__
    resource_id = instance.id
    
    if resource_type == 'Student':
        desc = f"Deleted student: {str(instance)}"
    elif resource_type == 'Teacher':
        desc = f"Deleted teacher: {str(instance)}"
    else:
        desc = f"Deleted {resource_type.lower()}: {str(instance)}"

    log_action(user, 'DELETE', resource_type, resource_id, desc)
