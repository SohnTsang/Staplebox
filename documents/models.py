from django.db import models
from django.utils import timezone
from products.models import Product
from folder.models import Folder  # Update this import based on your app structure
from document_types.models import DocumentType
import os
from django.utils.timezone import localtime
from django.conf import settings
from django.core.files.storage import default_storage
import logging
from django.core.exceptions import ValidationError
import uuid
from django.core.signing import Signer
import hashlib

signer = Signer()

logger = logging.getLogger(__name__)

def abbreviate(name, length=10):
    """
    Abbreviate the name to a maximum length by taking the first 'length' characters.
    """
    return name[:length] if name else None


def validate_file_size(file):
    max_file_size = 10 * 1024 * 1024  # 10 MB
    if file.size > max_file_size:
        raise ValidationError(f"The file size exceeds the limit of {max_file_size / (1024 * 1024)} MB.")

def document_upload_to(instance, filename):
    user_profile = instance.uploaded_by.userprofile
    company = user_profile.company_profiles.first()
    
    folder = instance.folder
    export = folder.exports.first() if folder.exports.exists() else None
    partner_name = None
    shared_folder_name = None

    if export:
        if export.partner.partner1 == company:
            partner_name = str(export.partner.partner2.uuid)  # Use UUID
        else:
            partner_name = str(export.partner.partner1.uuid)  # Use UUID

    partnership = folder.partnerships.first()
    if partnership and partnership.shared_folder:
        shared_folder_name = str(partnership.shared_folder.uuid)  # Use UUID

    # Use short names with UUIDs for better readability, exclude None values
    path_parts = [
        f"company_{abbreviate(str(company.uuid))}",  # Short name with UUID
        f"export_{abbreviate(str(export.uuid))}" if export else None,  # Short name with UUID
        f"partner_{abbreviate(partner_name)}" if partner_name else None,
        f"product_{abbreviate(str(folder.product.uuid))}" if folder.product else None,  # Short name with UUID
        f"shared_{abbreviate(shared_folder_name)}" if shared_folder_name else None,
        timezone.now().strftime('%Y%m%d')
    ]

    path_parts = [part for part in path_parts if part]  # Exclude None values
    return os.path.join('docs', *path_parts, filename)


def document_version_upload_to(instance, filename):
    user_profile = instance.uploaded_by.userprofile
    company = user_profile.company_profiles.first()

    document = instance.document
    folder = document.folder
    export = folder.exports.first() if folder.exports.exists() else None
    partner_name = None
    shared_folder_name = None

    if export:
        if export.partner.partner1 == company:
            partner_name = str(export.partner.partner2.uuid)  # Use UUID
        else:
            partner_name = str(export.partner.partner1.uuid)  # Use UUID

    partnership = folder.partnerships.first()
    if partnership and partnership.shared_folder:
        shared_folder_name = str(partnership.shared_folder.uuid)  # Use UUID

    # Use short names with UUIDs for better readability, exclude None values
    path_parts = [
        f"company_{abbreviate(str(company.uuid))}",  # Short name with UUID
        f"export_{abbreviate(str(export.uuid))}" if export else None,  # Short name with UUID
        f"partner_{abbreviate(partner_name)}" if partner_name else None,
        f"product_{abbreviate(str(folder.product.uuid))}" if folder.product else None,  # Short name with UUID
        f"shared_{abbreviate(shared_folder_name)}" if shared_folder_name else None,
        timezone.now().strftime('%Y%m%d')
    ]

    path_parts = [part for part in path_parts if part]  # Exclude None values
    return os.path.join('doc_ver', *path_parts, filename)


class Document(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
     

    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='documents')
    original_filename = models.CharField(max_length=255)
    document_type = models.ForeignKey(DocumentType, on_delete=models.SET_NULL, null=True, blank=True)
    file = models.FileField(upload_to=document_upload_to, max_length=500)
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='uploaded_documents')
    file_hash = models.CharField(max_length=64, blank=True, editable=False)  # SHA-256 hash strings are 64 characters
    comments = models.TextField(blank=True, null=True) 
    original_folder = models.ForeignKey(Folder, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    bin_expires_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
         
        validate_file_size(self.file)
        super().save(*args, **kwargs)
        
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
    
    @property
    def formatted_modified_date(self):
        return localtime(self.updated_at).strftime("%Y-%m-%d %H:%M")

    def update_version(self, new_file, new_hash, comments=None, uploaded_by=None):
        # Create a new DocumentVersion instance with the new file
        new_version = DocumentVersion.objects.create(
            document=self,
            file=new_file,
            version=self.version + 1,
            uploaded_by=uploaded_by if uploaded_by else self.uploaded_by,
            original_filename=new_file.name,
            file_hash=new_hash,
            comments=comments,
        )
        self.version = new_version.version
        self.file_hash = new_hash
        self.save()

    def delete(self, *args, **kwargs):
        # Delete the associated file from the storage
        if self.file and default_storage.exists(self.file.name):
            default_storage.delete(self.file.name)
        super().delete(*args, **kwargs)
    



class DocumentVersion(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
     

    document = models.ForeignKey(Document, related_name='versions', on_delete=models.CASCADE)
    file = models.FileField(upload_to=document_version_upload_to, max_length=500)
    version = models.IntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    uploaded_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True) 
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    original_filename = models.CharField(max_length=255)  # New field to store the filename
    file_hash = models.CharField(max_length=64, blank=True, editable=False)  # SHA-256 hash strings are 64 characters
    comments = models.TextField(blank=True, null=True)  # Add this line
    original_folder = models.ForeignKey(Folder, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    
    class Meta:
        unique_together = [('document', 'version')]

    @property
    def file_size(self):
        return self.file.size

    @property
    def formatted_file_size(self):
        return format_file_size(self.file.size)
    
    @property
    def formatted_modified_date(self):
        return localtime(self.updated_at).strftime("%Y-%m-%d %H:%M")
    
    def save(self, *args, **kwargs):
         
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        # Delete the associated file from the storage
        if self.file and default_storage.exists(self.file.name):
            default_storage.delete(self.file.name)
        super().delete(*args, **kwargs)

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