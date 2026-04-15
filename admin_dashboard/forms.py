from django import forms
from students.models import Student
from teachers.models import Teacher
from core.models import Subject, Class, Timetable, SchoolConfiguration
from accounts.models import User
from students.services import StudentService
from teachers.services import TeacherService

class StudentForm(forms.ModelForm):
    # Account fields
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    password = forms.CharField(widget=forms.PasswordInput, required=False)

    class Meta:
        model = Student
        fields = [
            'student_id', 'class_enrolled', 'enrollment_date',
            'age', 'gender', 'status', 'hobbies',
            'parent_name', 'parent_phone', 'parent_email', 'parent_relationship',
            'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relationship',
        ]
        widgets = {
            'enrollment_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student_id'].required = False
        if self.instance and self.instance.pk:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['password'].help_text = "Leave blank to keep current password"

    def clean_student_id(self):
        student_id = self.cleaned_data.get('student_id')
        if not student_id:
            return None
        if not self.instance.pk:
            if User.objects.filter(username=student_id).exists():
                raise forms.ValidationError(f'A user with ID "{student_id}" already exists.')
            if Student.objects.filter(student_id=student_id).exists():
                raise forms.ValidationError(f'Student ID "{student_id}" is already taken.')
        return student_id

    def clean(self):
        return super().clean()

    def save(self, commit=True):
        if not commit:
            return super().save(commit=False)

        user_data = {
            'first_name': self.cleaned_data['first_name'],
            'last_name': self.cleaned_data['last_name'],
            'password': self.cleaned_data.get('password'),
        }

        if self.instance and self.instance.pk:
            # Update existing student via service
            student_data = self.cleaned_data.copy()
            for key in ['first_name', 'last_name', 'password']:
                student_data.pop(key, None)
            
            student = StudentService.update_student(
                student_instance=self.instance,
                user_data=user_data,
                student_data=student_data
            )
        else:
            # Create new student via service
            student_data = self.cleaned_data.copy()
            student = StudentService.enroll_student(student_data)
            
            # Capture generated credentials for UI feedback (from service metadata)
            self.generated_password = getattr(student, '_generated_password', None)
            self.generated_username = getattr(student, '_generated_username', None)

        return student

class TeacherForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    gender = forms.ChoiceField(choices=User.GENDER_CHOICES, required=False)
    phone = forms.CharField(max_length=15, required=False)
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False)
    profile_picture = forms.ImageField(required=False)
    subjects = forms.ModelMultipleChoiceField(queryset=Subject.objects.all(), widget=forms.SelectMultiple(attrs={'class': 'form-control'}), required=False)

    class Meta:
        model = Teacher
        fields = [
            'teacher_id', 'department', 'qualification', 'specialization',
            'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relationship',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['teacher_id'].required = False
        if self.instance and self.instance.pk:
            user = self.instance.user
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['gender'].initial = user.gender
            self.fields['phone'].initial = user.phone
            self.fields['address'].initial = user.address
            self.fields['date_of_birth'].initial = user.date_of_birth
            self.initial['subjects'] = [s.pk for s in self.instance.subjects.all()]

    def clean_teacher_id(self):
        teacher_id = self.cleaned_data.get('teacher_id')
        if not teacher_id:
            return None
        if not self.instance.pk:
            if User.objects.filter(username=teacher_id).exists():
                raise forms.ValidationError(f'Teacher ID "{teacher_id}" already exists.')
        return teacher_id

    def clean(self):
        return super().clean()

    def save(self, commit=True):
        if not commit:
            return super().save(commit=False)

        user_data = {
            'first_name': self.cleaned_data['first_name'],
            'last_name': self.cleaned_data['last_name'],
            'email': self.cleaned_data['email'],
            'gender': self.cleaned_data.get('gender'),
            'phone': self.cleaned_data.get('phone'),
            'address': self.cleaned_data.get('address'),
            'date_of_birth': self.cleaned_data.get('date_of_birth'),
            'profile_picture': self.cleaned_data.get('profile_picture'),
            'password': self.cleaned_data.get('password'),
        }

        teacher_data = {
            'teacher_id': self.cleaned_data.get('teacher_id'),
            'department': self.cleaned_data.get('department'),
            'qualification': self.cleaned_data.get('qualification'),
            'specialization': self.cleaned_data.get('specialization'),
            'emergency_contact_name': self.cleaned_data.get('emergency_contact_name'),
            'emergency_contact_phone': self.cleaned_data.get('emergency_contact_phone'),
            'emergency_contact_relationship': self.cleaned_data.get('emergency_contact_relationship'),
        }

        subject_ids = [s.pk for s in self.cleaned_data.get('subjects', [])]

        if self.instance and self.instance.pk:
            teacher = TeacherService.update_teacher(
                teacher_instance=self.instance,
                user_data=user_data,
                teacher_data=teacher_data,
                subject_ids=subject_ids
            )
        else:
            teacher = TeacherService.onboard_teacher(
                user_data=user_data,
                teacher_data=teacher_data,
                subject_ids=subject_ids
            )
            # Capture generated credentials for UI feedback
            self.generated_password = getattr(teacher, '_generated_password', None)
            self.generated_username = getattr(teacher, '_generated_username', None)

        return teacher

class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

class ClassForm(forms.ModelForm):
    class_teacher = forms.ModelChoiceField(queryset=User.objects.filter(role='teacher'), empty_label="Select Class Teacher", required=False)
    class Meta:
        model = Class
        fields = ['name', 'section', 'grade', 'class_teacher']

class TimetableForm(forms.ModelForm):
    class Meta:
        model = Timetable
        fields = ['class_assigned', 'subject', 'teacher', 'day', 'start_time', 'end_time']
        widgets = {
            'class_assigned': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'teacher': forms.Select(attrs={'class': 'form-select'}),
            'day': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        class_assigned = cleaned_data.get('class_assigned')
        teacher = cleaned_data.get('teacher')
        day = cleaned_data.get('day')
        start = cleaned_data.get('start_time')
        end = cleaned_data.get('end_time')
        if start and end and start >= end:
            raise forms.ValidationError("Start time must be before end time.")
        if all([class_assigned, day, start, end]):
            overlaps_class = Timetable.objects.filter(class_assigned=class_assigned, day=day, start_time__lt=end, end_time__gt=start)
            if self.instance.pk:
                overlaps_class = overlaps_class.exclude(pk=self.instance.pk)
            if overlaps_class.exists():
                raise forms.ValidationError(f"Schedule conflict for {class_assigned}.")
            overlaps_teacher = Timetable.objects.filter(teacher=teacher, day=day, start_time__lt=end, end_time__gt=start)
            if self.instance.pk:
                overlaps_teacher = overlaps_teacher.exclude(pk=self.instance.pk)
            if overlaps_teacher.exists():
                raise forms.ValidationError(f"Teacher {teacher.get_full_name()} is already busy.")
        return cleaned_data

class SchoolSettingsForm(forms.ModelForm):
    """Form to manage global institutional configuration."""
    class Meta:
        model = SchoolConfiguration
        fields = [
            'name', 'motto', 'logo', 'contact_email', 'phone', 
            'address', 'current_academic_year', 'established_year',
            'currency_symbol', 'currency_code'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }

from core.models import AcademicTerm

class AcademicTermForm(forms.ModelForm):
    """Form to establish academic boundaries and holiday structure."""
    class Meta:
        model = AcademicTerm
        fields = ['name', 'session', 'start_date', 'end_date', 'vacation_duration', 'is_current']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }