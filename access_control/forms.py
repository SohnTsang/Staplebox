from django import forms
from django.contrib.auth.models import User
from .models import Folder, Document  # Adjust the import path based on your project structure
from django.db.models import Q
from .models import AccessPermission

class AccessPermissionForm(forms.Form):
    partners = forms.ModelMultipleChoiceField(queryset=User.objects.none(), widget=forms.CheckboxSelectMultiple(), required=False)
    remove_permissions = forms.ModelMultipleChoiceField(queryset=AccessPermission.objects.none(), widget=forms.CheckboxSelectMultiple(), required=False, label="Remove Access")
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        product_uuid = kwargs.pop('product_uuid', None)
        super().__init__(*args, **kwargs)

        if user:
            partner_users = User.objects.filter(Q(partnership_as_partner1__partner2=user) | Q(partnership_as_partner2__partner1=user), is_staff=False, is_active=True).distinct()
            self.fields['partners'].queryset = partner_users
        
        if product_uuid:
            self.fields['remove_permissions'].queryset = AccessPermission.objects.filter(product_id=product_uuid, partner1=user).select_related('partner2', 'folder', 'document')
            
            def custom_label_from_instance(obj):
                label = f"{obj.partner2.username} - Prod: {obj.product.product_name}"
                if obj.folder:
                    label += f", Folder: {obj.folder.name}"
                if obj.document:
                    label += f", Doc: {obj.document.display_filename}"
                return label
            
            self.fields['remove_permissions'].label_from_instance = custom_label_from_instance



