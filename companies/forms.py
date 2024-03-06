from django import forms
from .models import CompanyProfile

class CompanyProfileForm(forms.ModelForm):
    class Meta:
        model = CompanyProfile
        fields = ['name', 'role', 'address', 'phone_number', 'email', 'website', 'description']  # Add all the fields you want the user to fill out
