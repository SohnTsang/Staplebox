from django import forms
from django.contrib.auth.models import User
from .models import Folder, Document  # Adjust the import path based on your project structure
from django.db.models import Q
from .models import AccessPermission
from companies.models import CompanyProfile

class AccessPermissionForm(forms.Form):
    partners = forms.ModelMultipleChoiceField(queryset=CompanyProfile.objects.none(), widget=forms.CheckboxSelectMultiple(), required=False)
    remove_permissions = forms.ModelMultipleChoiceField(queryset=AccessPermission.objects.none(), widget=forms.CheckboxSelectMultiple(), required=False, label="Remove Access")
    
    def __init__(self, *args, **kwargs):
        company_profile = kwargs.pop('company_profile', None)
        product_uuid = kwargs.pop('product_uuid', None)
        super().__init__(*args, **kwargs)

        if company_profile:
            # Get the partner profiles related to the company profile
            partner_profiles = CompanyProfile.objects.filter(
                Q(partnership_as_partner1__partner2=company_profile) | 
                Q(partnership_as_partner2__partner1=company_profile)
            ).distinct()
            self.fields['partners'].queryset = partner_profiles
        
        if product_uuid:
            self.fields['remove_permissions'].queryset = AccessPermission.objects.filter(
                product__uuid=product_uuid,
                partner1=company_profile
            ).select_related('partner2', 'folder', 'document')
            
            def custom_label_from_instance(obj):
                label = f"{obj.partner2.name} - Prod: {obj.product.product_name}"
                if obj.folder:
                    label += f", Folder: {obj.folder.name}"
                if obj.document:
                    label += f", Doc: {obj.document.display_filename}"
                return label
            
            self.fields['remove_permissions'].label_from_instance = custom_label_from_instance



