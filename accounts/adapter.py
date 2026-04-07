from django.urls import reverse
from allauth.account.adapter import DefaultAccountAdapter

class CustomAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        """
        🛡️ Security: Public registration is strictly disabled.
        Accounts must be provisioned by an Administrator.
        """
        return False

    def get_login_redirect_url(self, request):
        """
        🎯 Dynamic Routing: Redirect users to their specific dashboard based on role.
        """
        user = request.user
        if user.is_authenticated:
            if hasattr(user, 'role'):
                if user.role == 'student':
                    return reverse('student_dashboard')
                elif user.role == 'teacher':
                    return reverse('teacher_dashboard')
                elif user.role == 'admin':
                    return reverse('admin_dashboard')
        
        return super().get_login_redirect_url(request)

    def get_signup_redirect_url(self, request):
        return self.get_login_redirect_url(request)
