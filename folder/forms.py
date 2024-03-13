from django import forms
from .models import Folder

class FolderForm(forms.ModelForm):
    class Meta:
        model = Folder
        fields = ['name', 'parent']

    def save(self, commit=True):
        folder = super().save(commit=False)
        # Ensure only one root folder per product
        if folder.is_root:
            Folder.objects.filter(product=folder.product, is_root=True).exclude(id=folder.id).update(is_root=False)
        if commit:
            folder.save()
        return folder
