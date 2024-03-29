from django.db import models
from django.utils import timezone
from products.models import Product
from folder.models import Folder  # Update this import based on your app structure
from document_types.models import DocumentType
import os
from django.utils.timezone import localtime
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile



class Document(models.Model):
    
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='documents')
    original_filename = models.CharField(max_length=255)
    document_type = models.ForeignKey(DocumentType, on_delete=models.CASCADE)
    file = models.FileField(upload_to='documents/%Y/%m/%d/')
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='uploaded_documents')
    file_hash = models.CharField(max_length=64, blank=True, editable=False)  # SHA-256 hash strings are 64 characters
    comments = models.TextField(blank=True, null=True)  # Add this line

    @property
    def display_filename(self):
        if self.versions.exists():
            return self.versions.latest('created_at').original_filename
        return self.original_filename

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
    
    @property
    def formatted_file_size(self):
        return format_file_size(self.file.size)

    def update_version(self, new_file, new_hash, comments=None):
    # Create a new DocumentVersion instance with the new file
        new_version = DocumentVersion.objects.create(
            document=self,
            file=new_file,
            version=self.version + 1,  # Increment version
            uploaded_by=self.uploaded_by,
            original_filename=new_file.name,
            file_hash=new_hash,  # Save the hash in DocumentVersion as well
            comments=comments,
        )

        # Update the Document to reference the latest version's file
        # Instead of saving the file again in the Document model, we update metadata
        self.version = new_version.version
        self.file_hash = new_hash
        # Optionally, if you want to keep the reference to the latest file in the Document as well, do so carefully
        # Note: This step can be skipped if you decide to always serve the latest file from the DocumentVersion model
        # This approach avoids duplication but maintains a reference to the latest file in the Document model
        self.file.name = new_version.file.name
        self.save()
    
    
    
class DocumentVersion(models.Model):
    document = models.ForeignKey(Document, related_name='versions', on_delete=models.CASCADE)
    file = models.FileField(upload_to='document_versions/%Y/%m/%d/')
    version = models.IntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    uploaded_at = models.DateTimeField(auto_now=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    original_filename = models.CharField(max_length=255)  # New field to store the filename
    file_hash = models.CharField(max_length=64, blank=True, editable=False)  # SHA-256 hash strings are 64 characters
    comments = models.TextField(blank=True, null=True)  # Add this line
    
    @property
    def file_size(self):
        return self.file.size

    @property
    def formatted_file_size(self):
        return format_file_size(self.file.size)

def format_file_size(size_in_bytes):
    """
    Convert file size in bytes to a more readable format, starting from KB.
    """
    if size_in_bytes < 1024:
        return "1 KB"  # Assume a minimum of 1 KB if the file size is less than 1024 bytes.
    size_in_kb = size_in_bytes / 1024.0  # Convert bytes to kilobytes first

    # Define file size units, starting from KB
    units = ['KB', 'MB', 'GB', 'TB', 'PB']
    for unit in units:
        if size_in_kb < 1024.0:
            return f"{size_in_kb:3.1f} {unit}"
        size_in_kb /= 1024.0
    return f"{size_in_kb:.1f} PB"  # Handle extremely large file sizes as well