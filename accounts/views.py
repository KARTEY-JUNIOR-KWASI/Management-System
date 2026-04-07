from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import login
from django.urls import reverse
from allauth.account import app_settings as account_settings

from .forms import CustomSignupForm, UserProfileForm

@login_required
def profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=request.user)
        
    student_profile = None
    teacher_profile = None
    
    if request.user.role == 'student':
        from students.models import Student
        student_profile = Student.objects.filter(user=request.user).first()
    elif request.user.role == 'teacher':
        from teachers.models import Teacher
        teacher_profile = Teacher.objects.filter(user=request.user).first()
        
    context = {
        'form': form,
        'student_profile': student_profile,
        'teacher_profile': teacher_profile
    }
    return render(request, 'accounts/profile.html', context)


def student_signup(request):
    if request.method == 'POST':
        form = CustomSignupForm(request.POST, request=request)
        if form.is_valid():
            user = form.save(request)
            if account_settings.EMAIL_VERIFICATION == 'mandatory':
                return redirect(reverse('account_login'))
            login(request, user)
            messages.success(request, 'Registration successful. Welcome to your student dashboard!')
            return redirect('student_dashboard')
    else:
        form = CustomSignupForm(request=request, initial={'role': 'student'})
    return render(request, 'accounts/student_signup.html', {'form': form})


def teacher_signup(request):
    if request.method == 'POST':
        form = CustomSignupForm(request.POST, request=request)
        if form.is_valid():
            user = form.save(request)
            if account_settings.EMAIL_VERIFICATION == 'mandatory':
                return redirect(reverse('account_login'))
            login(request, user)
            messages.success(request, 'Registration successful. Welcome to your teacher dashboard!')
            return redirect('teacher_dashboard')
    else:
        form = CustomSignupForm(request=request, initial={'role': 'teacher'})
    return render(request, 'accounts/teacher_signup.html', {'form': form})


