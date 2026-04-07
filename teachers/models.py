from django.db import models


class Teacher(models.Model):

    QUALIFICATION_CHOICES = [
        ('diploma', 'Diploma'),
        ('degree', 'Bachelor\'s Degree'),
        ('masters', 'Masters Degree'),
        ('phd', 'PhD'),
        ('other', 'Other'),
    ]

    # Core fields
    user = models.OneToOneField('accounts.User', on_delete=models.CASCADE)
    teacher_id = models.CharField(max_length=20, unique=True)
    subjects = models.ManyToManyField('core.Subject', related_name='teachers')
    hire_date = models.DateField(auto_now_add=True)

    # Professional info
    department = models.CharField(max_length=100, blank=True, help_text="Department (e.g. Science, Mathematics, Humanities)")
    qualification = models.CharField(max_length=20, choices=QUALIFICATION_CHOICES, blank=True)
    specialization = models.CharField(max_length=100, blank=True, help_text="Teaching specialization or area of expertise")

    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=100, blank=True, verbose_name="Emergency Contact Name")
    emergency_contact_phone = models.CharField(max_length=20, blank=True, verbose_name="Emergency Contact Phone")
    emergency_contact_relationship = models.CharField(max_length=30, blank=True, verbose_name="Relationship to Teacher")

    class Meta:
        indexes = [
            models.Index(fields=['teacher_id']),
        ]

    def __str__(self):
        return self.user.get_full_name() or self.teacher_id
