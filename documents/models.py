from django.db import models
from django.utils import timezone
from products.models import Product
from folder.models import Folder  # Update this import based on your app structure
from document_types.models import DocumentType
import os
from django.utils.timezone import localtime
from django.conf import settings



class Document(models.Model):
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='documents')
    document_type = models.ForeignKey(DocumentType, on_delete=models.CASCADE)
    file = models.FileField(upload_to='documents/%Y/%m/%d/')
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='uploaded_documents')



    @property
    def file_name(self):
        return os.path.basename(self.file.name)

    @property
    def file_size(self):
        return self.file.size

    @property
    def file_type(self):
        name, extension = os.path.splitext(self.file.name)
        return extension
    @property
    def formatted_upload_date(self):
        return localtime(self.created_at).strftime('%Y-%m-%d %H:%M:%S')