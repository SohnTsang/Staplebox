import logging

from django import forms
from allauth.account.forms import LoginForm
from allauth.account.forms import SignupForm as AllauthSignupForm

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.contrib.auth import password_validation
from django.utils.translation import gettext_lazy as _

from .validators import ValidateNotSameAsOldPassword, CustomPasswordValidator

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
    

class UpdateEmailForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email']

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already in use.")
        return email

class UpdatePasswordForm(PasswordChangeForm):
    new_password1 = forms.CharField(
        label="New password",
        widget=forms.PasswordInput,
        help_text=_("Your password must be at least 8 characters long and contain at least one uppercase letter and one lowercase letter."),
    )
    new_password2 = forms.CharField(
        label="Confirm new password",
        widget=forms.PasswordInput,
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super().__init__(self.user, *args, **kwargs)

    def clean_new_password1(self):
        new_password1 = self.cleaned_data.get('new_password1')

        # Collect errors in a list to avoid duplicates
        errors = []

        # Validate that the new password is not the same as the old one
        try:
            validator = ValidateNotSameAsOldPassword()
            validator.validate(new_password1, user=self.user)
        except ValidationError as e:
            if 'password_no_change' not in [err.code for err in e.error_list]:
                errors.extend(e.error_list)

        # Apply the custom password validation
        try:
            custom_validator = CustomPasswordValidator()
            custom_validator.validate(new_password1, user=self.user)
        except ValidationError as e:
            errors.extend(e.error_list)

        # Apply the default password validators
        try:
            password_validation.validate_password(new_password1, self.user)
        except ValidationError as e:
            errors.extend(e.error_list)

        # Raise all collected errors
        if errors:
            raise ValidationError(errors)

        return new_password1

    def clean(self):
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')

        if new_password1 and new_password2 and new_password1 != new_password2:
            self.add_error('new_password2', _("The two password fields didn’t match."))

        return cleaned_data