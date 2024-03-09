from django import forms
from .models import UserProfile
from companies.models import CompanyProfile
from allauth.account.forms import SignupForm, LoginForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.password_validation import validate_password


class CustomLoginForm(LoginForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(CustomLoginForm, self).__init__(*args, **kwargs)
        self.fields['login'].error_messages = {'required': 'Please enter your email.'}
        self.fields['login'].label = 'Email'
        self.fields['password'].error_messages = {'required': 'Please enter your password.'}





class SignupForm(SignupForm):

    def save(self, user):
        # Call the original save method to save the user and get the user object
        user = super(SignupForm, self).save(user)

        # Create or update the UserProfile instance
        userProfile, created = UserProfile.objects.get_or_create(user=user)
        companyProfile, company_created = CompanyProfile.objects.get_or_create(user_profile=userProfile)
        
        if company_created:
            companyProfile.name = "Company Name"  # Example of setting a default value
            companyProfile.save()
            
        userProfile.save()

        return user

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'passwordinput form-control'})




class PasswordResetRequestForm(forms.Form):
    username_or_email = forms.CharField(label="Username or Email")

    def clean_username_or_email(self):
        data = self.cleaned_data['username_or_email']

        if not User.objects.filter(username=data).exists() and not User.objects.filter(email=data).exists():
            raise ValidationError("A user with that username or email does not exist.")
        return data



class CustomPasswordChangeForm(PasswordChangeForm):
    def clean_new_password2(self):
        password2 = self.cleaned_data.get('new_password2')
        user = self.user
        validate_password(password2, user=user)  # Pass the user to the validator
        return password2
    


