from django import forms
from .models import Folder

class FolderForm(forms.ModelForm):
    class Meta:
        model = Folder
        fields = ['name', 'parent']
        exclude = ['product', 'created_by', 'is_root']

    def save(self, commit=True):
        folder = super().save(commit=False)
        # Ensure only one root folder per product
        if folder.is_root:
            Folder.objects.filter(product=folder.product, is_root=True).exclude(id=folder.uuid).update(is_root=False)
        if commit:
            folder.save()
        return folder
