from django import forms
from django.core.exceptions import ValidationError
from .models import Invitation
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User

class InvitationForm(forms.ModelForm):
    class Meta:
        model = Invitation
        fields = ['email']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(InvitationForm, self).__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        user_company_email = self.request.user.userprofile.company_profiles.first().email

        if email == user_company_email:
            raise ValidationError(_("You cannot send an invitation to yourself."))

        # Check if the email corresponds to an existing user with a company profile
        try:
            user = User.objects.get(email=email)
            company_profile = user.userprofile.company_profiles.first()
            if company_profile:
                email = company_profile.email
        except User.DoesNotExist:
            pass

        return email