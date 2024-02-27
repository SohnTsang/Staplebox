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
from users.views import login_signup_view
from users.views import password_reset_request
from django.contrib.auth import views as auth_views
from users.views import CustomPasswordResetCompleteView
from django.conf import settings
from django.conf.urls.static import static
from products.views import home_view  # Adjust the import based on your project structure


urlpatterns = [

    path('users/', include(('users.urls', 'users'), namespace='users')),
    path('folder/', include(('folder.urls', 'folder'), namespace='folder')),
    path('documents/', include(('documents.urls', 'documents'), namespace='documents')),
    path('products/', include('products.urls')),
    path('accounts/login/', login_signup_view, name='account_login'),
    path('accounts/signup/', login_signup_view, name='account_signup'),
    path('password/reset/complete/', CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    #path('password/reset/', password_reset_request, name='password_reset_request'),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),  # Assuming you're using django-allauth for authentication
    path('', home_view, name='home'),  # Directs to the home view for the root URL
    path('invitations/', include(('invitations.urls', 'invitations'), namespace='invitations')),
    path('partners/', include('partners.urls', namespace='partners')),
    path('access_control/', include('access_control.urls')),  # Include access_control URLs


] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
