from django import forms
from .models import CompanyProfile

class CompanyProfileForm(forms.ModelForm):
    class Meta:
        model = CompanyProfile
        fields = ['name', 'role', 'description', 'email', 'address', 'phone_number', 'website']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'maxlength': '2000'}),
            'address': forms.Textarea(attrs={'rows': 2}),
        }
        phone_number = forms.CharField(widget=forms.HiddenInput(), required=False)

    
    def __init__(self, *args, **kwargs):
        super(CompanyProfileForm, self).__init__(*args, **kwargs)
        self.fields['website'].required = False
        self.fields['address'].required = False
        self.fields['phone_number'].required = False
        self.fields['description'].required = False
        self.fields['website'].required = False
        self.fields['email'].required = False
        self.fields['name'].label = 'Company Name'
        self.fields['description'].label = 'About Us'


class CompanySelectionForm(forms.Form):
    new_company_name = forms.CharField(max_length=255, required=True, label='Create a new company')

    def clean_new_company_name(self):
        new_company_name = self.cleaned_data.get('new_company_name')
        if not new_company_name:
            raise forms.ValidationError("You must enter a new company name.")
        return new_company_name