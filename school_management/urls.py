"""
URL configuration for school_management project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts import views as account_views

from django.views.generic import RedirectView

urlpatterns = [
    path('accounts/logout/', RedirectView.as_view(pattern_name='account_logout'), name='logout'),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('profile/', include('accounts.urls')),
    path('', include('core.urls')),
    path('students/', include('students.urls')),
    path('teachers/', include('teachers.urls')),
    path('admin-dashboard/', include('admin_dashboard.urls')),
    path('analytics/', include('analytics.urls')),
    path('api/', include('api.urls')),
    path('library/', include('library.urls')),
    path('finance/', include('finance.urls', namespace='finance')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
