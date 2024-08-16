import logging

from django import forms
from allauth.account.forms import LoginForm
from allauth.account.forms import SignupForm as AllauthSignupForm

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

logger = logging.getLogger(__name__)

class CustomLoginForm(LoginForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(CustomLoginForm, self).__init__(*args, **kwargs)
        self.fields['login'].error_messages = {'required': 'Please enter your email.'}
        self.fields['login'].label = 'Email'
        self.fields['password'].error_messages = {'required': 'Please enter your password.'}


class SignupForm(AllauthSignupForm):
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            logger.warning(f"Signup attempt with existing email: {email}")
            raise ValidationError("A user with that email already exists.")
        return email

    @transaction.atomic
    def save(self, request):
        # Call the original save method to save the user and get the user object
        user = super(SignupForm, self).save(request)
        logger.info(f"User {user.email} created successfully.")
        return user

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'passwordinput form-control'})



class PasswordResetRequestForm(forms.Form):
    username_or_email = forms.CharField(label="Username or Email")

    def clean_username_or_email(self):
        data = self.cleaned_data['username_or_email']

        if not User.objects.filter(username=data).exists() and not User.objects.filter(email=data).exists():
            logger.warning(f"Password reset request for non-existent user: {data}")
            raise ValidationError("A user with that username or email does not exist.")
        return data



class CustomPasswordChangeForm(PasswordChangeForm):
    def clean_new_password2(self):
        password2 = self.cleaned_data.get('new_password2')
        user = self.user
        validate_password(password2, user=user)  # Pass the user to the validator
        return password2
    


