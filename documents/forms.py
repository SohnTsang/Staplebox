'''

from django import forms
from .models import Document

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['folder', 'document_type', 'file']

'''

from django import forms
from .models import Document, DocumentType, Folder
from document_types.models import DocumentType


class DocumentUploadForm(forms.ModelForm):
    document_type = forms.ModelChoiceField(queryset=DocumentType.objects.all(), required=True)

    class Meta:
        model = Document
        fields = ['file', 'document_type']


class DocumentEditForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['document_type', 'original_filename', 'comments']
    
    def __init__(self, *args, **kwargs):
        super(DocumentEditForm, self).__init__(*args, **kwargs)
        # Add placeholders or customize fields as needed
        self.fields['document_type'].queryset = DocumentType.objects.all()