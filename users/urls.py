from django.urls import path, include
from . import views
from django.contrib.auth import views as auth_views
from .views import password_reset_request, CustomPasswordResetCompleteView

app_name = 'users'

urlpatterns = [
    path('password/reset/confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name="account/password_reset_confirm.html"),
         name='password_reset_confirm'),
    path('password/reset/complete/', CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('password/reset/', password_reset_request, name='password_reset_request'),

    # You should also create a view for 'custom_password_reset_done' that shows a success message.
]