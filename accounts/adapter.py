from django.urls import reverse
from allauth.account.adapter import DefaultAccountAdapter


class CustomAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        user = request.user
        if user.is_authenticated:
            if user.role == 'student':
                return reverse('student_dashboard')
            if user.role == 'teacher':
                return reverse('teacher_dashboard')
            if user.role == 'admin':
                return reverse('admin_dashboard')
        return super().get_login_redirect_url(request)

    def get_signup_redirect_url(self, request):
        return self.get_login_redirect_url(request)
