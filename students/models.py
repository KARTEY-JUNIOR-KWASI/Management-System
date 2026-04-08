from django.db import models
from django.db.models import Avg, Count, Q, F, ExpressionWrapper, FloatField, Case, When
from django.db.models.functions import Coalesce, Cast


class StudentQuerySet(models.QuerySet):
    def with_performance_stats(self):
        """
        Annotates the queryset with attendance_rate and gpa.
        Reduces O(N) queries to O(1).
        """
        return self.annotate(
            # Attendance stats
            total_days_count=Count('attendances', distinct=True),
            present_days_count=Count('attendances', filter=Q(attendances__status='present'), distinct=True),
            annotated_attendance_rate=Case(
                When(total_days_count__gt=0, then=ExpressionWrapper(
                    F('present_days_count') * 100.0 / F('total_days_count'),
                    output_field=FloatField()
                )),
                default=0.0,
                output_field=FloatField()
            ),
            # GPA Stats: AVG( (score/max_score) * 4.0 )
            # Fix: Explicitly cast Decimals to Float for PostgreSQL compatibility
            annotated_gpa=Coalesce(
                Avg(
                    Case(
                        When(results__max_score__gt=0, then=ExpressionWrapper(
                            Cast(F('results__score'), FloatField()) * 4.0 / Cast(F('results__max_score'), FloatField()),
                            output_field=FloatField()
                        )),
                        default=0.0,
                        output_field=FloatField()
                    )
                ),
                0.0
            )
        )


class StudentManager(models.Manager):
    def get_queryset(self):
        return StudentQuerySet(self.model, using=self._db)

    def with_performance_stats(self):
        return self.get_queryset().with_performance_stats()


class Student(models.Model):

    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('graduated', 'Graduated'),
    ]

    # Core fields
    user = models.OneToOneField('accounts.User', on_delete=models.CASCADE)
    student_id = models.CharField(max_length=20, unique=True)
    class_enrolled = models.ForeignKey('core.Class', on_delete=models.SET_NULL, null=True, blank=True)
    enrollment_date = models.DateField(null=True, blank=True, help_text="Date the student was admitted to the school")

    # Personal Info
    age = models.PositiveIntegerField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    hobbies = models.TextField(blank=True, help_text="Student's hobbies and interests")

    # Parent / Guardian Info
    parent_name = models.CharField(max_length=100, blank=True, verbose_name="Parent / Guardian Name")
    parent_phone = models.CharField(max_length=20, blank=True, verbose_name="Parent / Guardian Phone")
    parent_email = models.EmailField(blank=True, verbose_name="Parent / Guardian Email")
    parent_relationship = models.CharField(
        max_length=30, blank=True,
        verbose_name="Relationship to Student",
        help_text="e.g. Father, Mother, Uncle, Guardian"
    )

    # Emergency Contact (can be different from parent)
    emergency_contact_name = models.CharField(max_length=100, blank=True, verbose_name="Emergency Contact Name")
    emergency_contact_phone = models.CharField(max_length=20, blank=True, verbose_name="Emergency Contact Phone")
    emergency_contact_relationship = models.CharField(max_length=30, blank=True, verbose_name="Emergency Relationship")

    objects = StudentManager()

    class Meta:
        indexes = [
            models.Index(fields=['student_id']),
            models.Index(fields=['class_enrolled']),
            models.Index(fields=['status']),
            models.Index(fields=['enrollment_date']),
        ]

    def __str__(self):
        full_name = self.user.get_full_name()
        if full_name and full_name.strip():
            return full_name.strip()
        return self.student_id

    @property
    def attendance_percentage(self):
        # Use annotated value if available for performance
        if hasattr(self, 'annotated_attendance_rate'):
            return round(self.annotated_attendance_rate, 1)
            
        # Fallback to O(N) calculation for backward compatibility/single lookups
        attendances = list(self.attendances.all())
        total_days = len(attendances)
        present_days = sum(1 for a in attendances if a.status == 'present')
        return round((present_days / total_days * 100), 1) if total_days > 0 else 0

    @property
    def gpa(self):
        # Use annotated value if available for performance
        if hasattr(self, 'annotated_gpa'):
            return round(self.annotated_gpa, 2)

        # Fallback to O(N) calculation
        results = list(self.results.all())
        if results:
            total_score = sum((float(r.score) / float(r.max_score)) for r in results if r.max_score and r.max_score > 0)
            return round(total_score / len(results) * 4.0, 2)
        return 0.0
