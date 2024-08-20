import logging
from django import forms
from .models import CompanyProfile
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

logger = logging.getLogger(__name__)

class CompanyProfileForm(forms.ModelForm):
    class Meta:
        model = CompanyProfile
        fields = [
            'name', 'role', 'description', 'email', 'address', 'phone_number', 
            'website', 'primary_contact_name', 'primary_contact_email', 
            'linkedin', 'facebook', 'twitter', 'profile_image'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 6, 'maxlength': '1000'}),
            'address': forms.Textarea(attrs={'rows': 2}),
            'role': forms.Select(attrs={'style': 'width: 100%;'}),
        }
        phone_number = forms.CharField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        super(CompanyProfileForm, self).__init__(*args, **kwargs)

        # Remove any default URLValidator if applied
        # Remove any default URLValidator
        for field_name in ['linkedin', 'facebook', 'twitter']:
            field = self.fields.get(field_name)
            if field:
                field.validators = [v for v in field.validators if not isinstance(v, URLValidator)]

        # Set required=False for optional fields, required=True for mandatory fields
        self.fields['name'].required = True  # Ensure this is required
        self.fields['role'].required = False
        self.fields['description'].required = False
        self.fields['email'].required = True  # Assuming email is required
        self.fields['address'].required = False
        self.fields['phone_number'].required = False
        self.fields['website'].required = False
        self.fields['primary_contact_name'].required = False
        self.fields['primary_contact_email'].required = False
        self.fields['linkedin'].required = False
        self.fields['facebook'].required = False
        self.fields['twitter'].required = False
        self.fields['name'].label = 'Company Name'
        self.fields['description'].label = 'About Us'

    def clean(self):
        cleaned_data = super().clean()
        
        linkedin = cleaned_data.get('linkedin')
        if linkedin:
            cleaned_data['linkedin'] = self.clean_linkedin()
        
        # Continue with other fields
        facebook = cleaned_data.get('facebook')
        if facebook:
            cleaned_data['facebook'] = self.clean_facebook()
        
        twitter = cleaned_data.get('twitter')
        if twitter:
            cleaned_data['twitter'] = self.clean_twitter()

        return cleaned_data

    def clean_linkedin(self):
        linkedin = self.cleaned_data.get('linkedin')  # Access cleaned data

        if linkedin:  # Proceed only if the field is not empty
            if not (linkedin.startswith("https://www.linkedin.com/") or 
                    not linkedin.startswith("http://www.linkedin.com/") or
                    not linkedin.startswith("www.linkedin.com/") or 
                    not linkedin.startswith("linkedin.com/")):
                raise ValidationError("Please enter a valid LinkedIn profile URL")
        else:
            logger.debug("LinkedIn field is empty, skipping validation.")

        return linkedin


    def clean_facebook(self):
        facebook = self.cleaned_data.get('facebook')

        if facebook:  # Proceed only if the field is not empty
            if not (facebook.startswith("https://www.facebook.com/") or 
                    not facebook.startswith("http://www.facebook.com/") or
                    not facebook.startswith("www.facebook.com/") or 
                    not facebook.startswith("facebook.com/")):
                raise ValidationError("Please enter a valid Facebook profile URL")
        return facebook

    def clean_twitter(self):
        twitter = self.cleaned_data.get('twitter')

        if twitter:  # Proceed only if the field is not empty
            if not (twitter.startswith("https://x.com/") or 
                    not twitter.startswith("http://x.com/") or
                    not twitter.startswith("www.x.com/") or 
                    not twitter.startswith("x.com/")):
                raise ValidationError("Please enter a valid X profile URL")
        return twitter
    


class CompanySelectionForm(forms.Form):
    new_company_name = forms.CharField(max_length=255, required=True, label='Create a new company')

    def clean_new_company_name(self):
        new_company_name = self.cleaned_data.get('new_company_name')
        if not new_company_name:
            raise forms.ValidationError("You must enter a new company name.")
        return new_company_name