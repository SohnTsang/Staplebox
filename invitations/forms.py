from django import forms
from django.core.exceptions import ValidationError
from .models import Invitation
from django.utils.translation import gettext_lazy as _

class InvitationForm(forms.ModelForm):
    class Meta:
        model = Invitation
        fields = ['email']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(InvitationForm, self).__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email == self.request.user.email:
            raise ValidationError(_("You cannot send an invitation to yourself."))
            
        return email