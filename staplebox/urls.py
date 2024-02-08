"""
URL configuration for staplebox project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
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
# staplebox/urls.py

from django.contrib import admin
from django.urls import path, include
from users import views as user_views  # Import the view function from your users app
from users.views import LoginView
from users.views import password_reset_request
from django.contrib.auth import views as auth_views
from users.views import CustomPasswordResetCompleteView

urlpatterns = [

    path('users/', include(('users.urls', 'users'), namespace='users')),
    path('accounts/login/', LoginView.as_view(), name='account_login'),

    path('password/reset/complete/', CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    #path('password/reset/', password_reset_request, name='password_reset_request'),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),  # Assuming you're using django-allauth for authentication
    path('', user_views.home, name='home'),  # Directs to the home view for the root URL

]
