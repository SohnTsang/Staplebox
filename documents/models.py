from django.db import models
from django.utils import timezone
from products.models import Product
from folder.models import Folder  # Update this import based on your app structure
from document_types.models import DocumentType

class Document(models.Model):
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='documents')  # Changed from product to folder
    document_type = models.ForeignKey(DocumentType, on_delete=models.CASCADE)
    file = models.FileField(upload_to='documents/%Y/%m/%d/')
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
