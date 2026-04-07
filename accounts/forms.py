from django import forms
from allauth.account.forms import SignupForm
from .models import User

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'gender', 'phone', 'address', 'date_of_birth', 'profile_picture']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }

class CustomSignupForm(SignupForm):
    role = forms.ChoiceField(choices=User.ROLE_CHOICES, required=True, label="Role")
    gender = forms.ChoiceField(choices=User.GENDER_CHOICES, required=False, label="Gender")

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        from core.models import Class as SchoolClass

        self.fields['class_enrolled'] = forms.ModelChoiceField(
            queryset=SchoolClass.objects.all(),
            required=False,
            label='Enroll in class',
            empty_label='Select class'
        )

        role = None
        if self.request:
            role = self.request.GET.get('role')
        if not role:
            role = self.initial.get('role')

        if role in dict(User.ROLE_CHOICES):
            self.fields['role'].initial = role
            if role == 'student':
                self.fields['role'].widget = forms.HiddenInput()
                self.fields['class_enrolled'].required = True
            else:
                self.fields['class_enrolled'].widget = forms.HiddenInput()
        else:
            self.fields['class_enrolled'].widget = forms.HiddenInput()

    def save(self, request):
        user = super().save(request)
        user.role = self.cleaned_data['role']
        user.save()

        user.gender = self.cleaned_data.get('gender')
        user.save()

        if user.role == 'student':
            from students.models import Student
            class_enrolled = self.cleaned_data.get('class_enrolled')
            student, created = Student.objects.get_or_create(
                user=user,
                defaults={
                    'student_id': f'STUD{user.id:05d}',
                    'class_enrolled': class_enrolled,
                }
            )
            if not created and class_enrolled:
                student.class_enrolled = class_enrolled
                student.save()

        return user