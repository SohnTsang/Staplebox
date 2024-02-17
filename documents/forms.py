'''

from django import forms
from .models import Document

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['folder', 'document_type', 'file']

'''

from django import forms
from .models import Document
from document_types.models import DocumentType

class DocumentUploadForm(forms.ModelForm):
    document_type = forms.ModelChoiceField(queryset=DocumentType.objects.all(), required=True)

    class Meta:
        model = Document
        fields = ['file', 'document_type']