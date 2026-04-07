from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User


@receiver(post_save, sender=User)
def create_role_profile(sender, instance, created, **kwargs):
    if kwargs.get('raw'):
        return
    if not created:
        return

    if instance.role == 'student':
        from students.models import Student
        Student.objects.get_or_create(
            user=instance,
            defaults={
                'student_id': f'STUD{instance.id:05d}',
            }
        )
    elif instance.role == 'teacher':
        from teachers.models import Teacher
        Teacher.objects.get_or_create(
            user=instance,
            defaults={
                'teacher_id': f'TCHR{instance.id:05d}',
            }
        )
