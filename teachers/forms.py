from django import forms
from django.forms import modelformset_factory
from core.models import Attendance, Class, Subject, Result, Assignment
from students.models import Student
from .models import Teacher
from datetime import date

class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

class AttendanceDateForm(forms.Form):
    date = forms.DateField(
        initial=date.today,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    class_id = forms.ModelChoiceField(
        queryset=Class.objects.none(),  # Will be set in view
        empty_label="Select Class",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['class_id'].queryset = Class.objects.filter(class_teacher=user)

AttendanceFormSet = modelformset_factory(
    Attendance,
    form=AttendanceForm,
    extra=0,
    can_delete=False
)

class GradeForm(forms.ModelForm):
    class Meta:
        model = Result
        fields = ['exam_type', 'score', 'max_score']
        widgets = {
            'exam_type': forms.Select(attrs={'class': 'form-select'}),
            'score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'max_score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class GradeSelectionForm(forms.Form):
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.none(),
        empty_label="Select Subject",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    class_id = forms.ModelChoiceField(
        queryset=Class.objects.none(),
        empty_label="Select Class",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    student = forms.ModelChoiceField(
        queryset=Student.objects.none(),
        empty_label="Select Student",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            # Get subjects taught by this teacher
            try:
                teacher = Teacher.objects.get(user=user)
                self.fields['subject'].queryset = teacher.subjects.all()
            except Teacher.DoesNotExist:
                self.fields['subject'].queryset = Subject.objects.none()
            # Get all classes this teacher can access
            from django.db.models import Q as QQ
            direct = Class.objects.filter(class_teacher=user)
            via_assignments = Class.objects.filter(assignments__teacher=user).distinct()
            all_ids = set(list(direct.values_list('id', flat=True)) + list(via_assignments.values_list('id', flat=True)))
            if all_ids:
                self.fields['class_id'].queryset = Class.objects.filter(id__in=all_ids)
            else:
                self.fields['class_id'].queryset = Class.objects.all()

    def update_students(self, class_id):
        if class_id:
            self.fields['student'].queryset = Student.objects.filter(class_enrolled=class_id)

class BulkGradeForm(forms.Form):
    exam_type = forms.ChoiceField(
        choices=[('midterm', 'Midterm'), ('final', 'Final'), ('quiz', 'Quiz')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    max_score = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        initial=100,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )

    def __init__(self, *args, **kwargs):
        students = kwargs.pop('students', [])
        super().__init__(*args, **kwargs)

        for student in students:
            self.fields[f'score_{student.id}'] = forms.DecimalField(
                max_digits=5,
                decimal_places=2,
                required=False,
                widget=forms.NumberInput(attrs={
                    'class': 'form-control',
                    'step': '0.01',
                    'placeholder': 'Enter score'
                })
            )

class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['title', 'description', 'subject', 'class_assigned', 'due_date', 'file']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'class_assigned': forms.Select(attrs={'class': 'form-control'}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            # Get subjects taught by this teacher
            try:
                teacher = Teacher.objects.get(user=user)
                self.fields['subject'].queryset = teacher.subjects.all()
            except Teacher.DoesNotExist:
                self.fields['subject'].queryset = Subject.objects.none()
            # Get all classes this teacher can access
            from django.db.models import Q as QQ
            direct = Class.objects.filter(class_teacher=user)
            via_assignments = Class.objects.filter(assignments__teacher=user).distinct()
            all_ids = set(list(direct.values_list('id', flat=True)) + list(via_assignments.values_list('id', flat=True)))
            if all_ids:
                self.fields['class_assigned'].queryset = Class.objects.filter(id__in=all_ids)
            else:
                self.fields['class_assigned'].queryset = Class.objects.all()