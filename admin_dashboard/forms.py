from django import forms
from students.models import Student
from teachers.models import Teacher
from core.models import Subject, Class
from accounts.models import User
from accounts.utils import generate_user_id, generate_random_password


class StudentForm(forms.ModelForm):
    # Account fields
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    password = forms.CharField(widget=forms.PasswordInput, required=False)

    class Meta:
        model = Student
        fields = [
            'student_id', 'class_enrolled', 'enrollment_date',
            # Personal Info
            'age', 'gender', 'status', 'hobbies',
            # Parent / Guardian
            'parent_name', 'parent_phone', 'parent_email', 'parent_relationship',
            # Emergency Contact
            'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relationship',
        ]
        widgets = {
            'enrollment_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['password'].help_text = "Leave blank to keep current password"

    def clean_student_id(self):
        student_id = self.cleaned_data.get('student_id')
        if not self.instance.pk:
            if User.objects.filter(username=student_id).exists():
                raise forms.ValidationError(
                    f'A user with ID "{student_id}" already exists. Please generate a different ID.'
                )
            if Student.objects.filter(student_id=student_id).exists():
                raise forms.ValidationError(
                    f'Student ID "{student_id}" is already taken. Please generate a new one.'
                )
        return student_id

    def clean(self):
        cleaned_data = super().clean()
        if not self.instance.pk and not cleaned_data.get('password'):
            self.add_error('password', 'Password is required when creating a new student.')
        return cleaned_data

    def save(self, commit=True):
        if self.instance and self.instance.pk:
            user = self.instance.user
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            if self.cleaned_data.get('password'):
                user.set_password(self.cleaned_data['password'])
            user.save()
            student = super().save(commit=commit)
        else:
            # AUTO-GENERATE credentials for new students
            username = generate_user_id('student')
            password = generate_random_password(12)
            
            user = User.objects.create_user(
                username=username,
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name'],
                password=password,
                role='student'
            )
            
            # Store generated password temporarily so view can show it
            self.generated_password = password
            self.generated_username = username
            
            student, created = Student.objects.get_or_create(user=user)
            student.student_id = username
            student.class_enrolled = self.cleaned_data.get('class_enrolled')
            student.enrollment_date = self.cleaned_data.get('enrollment_date')
            student.age = self.cleaned_data.get('age')
            student.gender = self.cleaned_data.get('gender', '')
            student.status = self.cleaned_data.get('status', 'active')
            student.hobbies = self.cleaned_data.get('hobbies', '')
            
            # Parent/Guardian
            student.parent_name = self.cleaned_data.get('parent_name', '')
            student.parent_phone = self.cleaned_data.get('parent_phone', '')
            student.parent_email = self.cleaned_data.get('parent_email', '')
            student.parent_relationship = self.cleaned_data.get('parent_relationship', '')
            
            # Emergency
            student.emergency_contact_name = self.cleaned_data.get('emergency_contact_name', '')
            student.emergency_contact_phone = self.cleaned_data.get('emergency_contact_phone', '')
            student.emergency_contact_relationship = self.cleaned_data.get('emergency_contact_relationship', '')

            if commit:
                student.save()
        return student


class TeacherForm(forms.ModelForm):
    # Account fields
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    
    # User Profile fields
    gender = forms.ChoiceField(choices=User.GENDER_CHOICES, required=False)
    phone = forms.CharField(max_length=15, required=False)
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False)
    profile_picture = forms.ImageField(required=False)
    
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
        required=False
    )

    class Meta:
        model = Teacher
        fields = [
            'teacher_id', 'department',
            'qualification', 'specialization',
            'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relationship',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            user = self.instance.user
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['gender'].initial = user.gender
            self.fields['phone'].initial = user.phone
            self.fields['address'].initial = user.address
            self.fields['date_of_birth'].initial = user.date_of_birth
            self.fields['password'].help_text = "Leave blank to keep current password"
            self.initial['subjects'] = [s.pk for s in self.instance.subjects.all()]

    def clean_teacher_id(self):
        teacher_id = self.cleaned_data.get('teacher_id')
        if not self.instance.pk:
            if User.objects.filter(username=teacher_id).exists():
                raise forms.ValidationError(
                    f'A user with ID "{teacher_id}" already exists. Please generate a different ID.'
                )
            if Teacher.objects.filter(teacher_id=teacher_id).exists():
                raise forms.ValidationError(
                    f'Teacher ID "{teacher_id}" is already taken. Please generate a new one.'
                )
        return teacher_id

    def clean(self):
        cleaned_data = super().clean()
        if not self.instance.pk and not cleaned_data.get('password'):
            self.add_error('password', 'Password is required when creating a new teacher.')
        return cleaned_data

    def save(self, commit=True):
        if self.instance and self.instance.pk:
            user = self.instance.user
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.email = self.cleaned_data['email']
            user.gender = self.cleaned_data['gender']
            user.phone = self.cleaned_data['phone']
            user.address = self.cleaned_data['address']
            user.date_of_birth = self.cleaned_data['date_of_birth']
            if self.cleaned_data.get('profile_picture'):
                user.profile_picture = self.cleaned_data['profile_picture']
                
            if self.cleaned_data.get('password'):
                user.set_password(self.cleaned_data['password'])
            user.save()
            teacher = super().save(commit=commit)
            teacher.subjects.set(self.cleaned_data.get('subjects', []))
        else:
            # AUTO-GENERATE credentials for new teachers
            username = generate_user_id('teacher')
            password = generate_random_password(12)
            
            user = User.objects.create_user(
                username=username,
                email=self.cleaned_data['email'],
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name'],
                password=password,
                role='teacher'
            )
            
            # Store generated password temporarily so view can show it
            self.generated_password = password
            self.generated_username = username
            
            # Add supplemental profile details
            user.gender = self.cleaned_data['gender']
            user.phone = self.cleaned_data['phone']
            user.address = self.cleaned_data['address']
            user.date_of_birth = self.cleaned_data['date_of_birth']
            if self.cleaned_data.get('profile_picture'):
                user.profile_picture = self.cleaned_data['profile_picture']
            user.save()
            
            teacher, created = Teacher.objects.get_or_create(user=user)
            teacher.teacher_id = username
            teacher.department = self.cleaned_data.get('department', '')
            teacher.qualification = self.cleaned_data.get('qualification', '')
            teacher.specialization = self.cleaned_data.get('specialization', '')
            teacher.emergency_contact_name = self.cleaned_data.get('emergency_contact_name', '')
            teacher.emergency_contact_phone = self.cleaned_data.get('emergency_contact_phone', '')
            teacher.emergency_contact_relationship = self.cleaned_data.get('emergency_contact_relationship', '')
            teacher.save()
            
            if self.cleaned_data.get('subjects'):
                teacher.subjects.set(self.cleaned_data.get('subjects'))
                
        return teacher


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class ClassForm(forms.ModelForm):
    class_teacher = forms.ModelChoiceField(
        queryset=User.objects.filter(role='teacher'),
        empty_label="Select Class Teacher",
        required=False
    )

    class Meta:
        model = Class
        fields = ['name', 'section', 'grade', 'class_teacher']

from core.models import Timetable

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
            # Check for class overlaps
            overlaps_class = Timetable.objects.filter(
                class_assigned=class_assigned,
                day=day,
                start_time__lt=end,
                end_time__gt=start
            )
            if self.instance.pk:
                overlaps_class = overlaps_class.exclude(pk=self.instance.pk)
            if overlaps_class.exists():
                raise forms.ValidationError(f"Schedule conflict for {class_assigned}. Another class starts at {overlaps_class.first().start_time}.")

            # Check for teacher overlaps
            overlaps_teacher = Timetable.objects.filter(
                teacher=teacher,
                day=day,
                start_time__lt=end,
                end_time__gt=start
            )
            if self.instance.pk:
                overlaps_teacher = overlaps_teacher.exclude(pk=self.instance.pk)
            if overlaps_teacher.exists():
                raise forms.ValidationError(f"Teacher {teacher.get_full_name()} is already busy during this time.")

        return cleaned_data