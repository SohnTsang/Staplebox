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
    document_type = forms.ModelChoiceField(queryset=DocumentType.objects.all(), required=False)  # Make it optional

    class Meta:
        model = Document
        fields = ['file', 'document_type']


class DocumentEditForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['document_type', 'original_filename', 'comments']
    
    def __init__(self, *args, **kwargs):
        super(DocumentEditForm, self).__init__(*args, **kwargs)
        self.fields['document_type'].queryset = DocumentType.objects.all()
        
        # Set the default selection for the document_type field
        if not self.instance.pk:  # Check if the form is for a new instance
            first_document_type = DocumentType.objects.first()  # Get the first DocumentType
            if first_document_type:
                self.fields['document_type'].initial = first_document_type.id