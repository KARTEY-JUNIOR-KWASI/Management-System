from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Student
from .services import StudentService

@receiver(post_save, sender=Student)
def automate_house_assignment(sender, instance, created, **kwargs):
    """
    Automated signal to ensure every new student is assigned to 
    an institutional house if one hasn't been specified.
    """
    if kwargs.get('raw'):
        return

    # Only assign house if not already set (e.g. during enrollment or signup)
    if not instance.house:
        # We use the Service to ensure the logic isn't duplicated
        StudentService.assign_automated_house(instance)
