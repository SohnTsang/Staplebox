from django import forms
from django.contrib.auth.models import User
from .models import Folder, Document  # Adjust the import path based on your project structure
from django.db.models import Q
from .models import AccessPermission

class AccessPermissionForm(forms.Form):
    partners = forms.ModelMultipleChoiceField(queryset=User.objects.none(), widget=forms.CheckboxSelectMultiple(), required=False)
    folders = forms.ModelMultipleChoiceField(queryset=Folder.objects.none(), widget=forms.CheckboxSelectMultiple(), required=False)
    documents = forms.ModelMultipleChoiceField(queryset=Document.objects.none(), widget=forms.CheckboxSelectMultiple(), required=False)
    remove_permissions = forms.ModelMultipleChoiceField(
        queryset=AccessPermission.objects.none(),  # This will be set dynamically
        widget=forms.CheckboxSelectMultiple(),
        required=False,
        label="Remove Access"
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        product_id = kwargs.pop('product_id', None)
        super().__init__(*args, **kwargs)
        if user:
            # Fetch all partners related to the current user, either as partner1 or partner2, excluding admin users
            partner_users = User.objects.filter(
                Q(partnership_as_partner1__partner2=user) | Q(partnership_as_partner2__partner1=user),
                is_staff=False,  # Exclude admin users assuming they're marked with is_staff=True
                is_active=True   # Assuming you want to consider only active users
            ).distinct()

            self.fields['partners'].queryset = partner_users
            
        
        if product_id:

            self.fields['folders'].queryset = Folder.objects.filter(product_id=product_id)
            self.fields['folders'].label_from_instance = lambda obj: f"{obj.name}, Modified: {obj.updated_at.strftime('%Y-%m-%d')}"
            self.fields['documents'].queryset = Document.objects.filter(folder__product_id=product_id)
            self.fields['documents'].label_from_instance = lambda obj: f"{obj.display_filename} - Type: {obj.document_type}, Modified: {obj.updated_at.strftime('%Y-%m-%d')}"
            self.fields['remove_permissions'].queryset = AccessPermission.objects.filter(
                product_id=product_id,
                partner1=user
            ).select_related('partner2', 'folder', 'document')

            def custom_label_from_instance(obj):
                label = f"{obj.partner2.username} - Prod: {obj.product.product_name}"
                if obj.folder:
                    label += f", Folder: {obj.folder.name}"
                if obj.document:
                    label += f", Doc: {obj.document.display_filename}"
                return label
            
            self.fields['remove_permissions'].label_from_instance = custom_label_from_instance


