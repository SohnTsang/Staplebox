from django.db import models
from products.models import Product
from django.utils import timezone
from django.conf import settings
from rest_framework import serializers
import uuid
from django.core.signing import Signer

signer = Signer()

class Folder(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
     

    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfolders')

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='folders', null=True, blank=True)
    is_root = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_folders')
    original_parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    is_bin = models.BooleanField(default=False)  # Indicates if the folder is a bin
    bin_expires_at = models.DateTimeField(null=True, blank=True)
    
    def get_ancestors(self, include_self=False):
        ancestors = []
        current = self if include_self else self.parent
        while current is not None:
            ancestors.insert(0, current)
            current = current.parent
        return ancestors

    def save(self, *args, **kwargs):
        if self.is_root:
            # If this folder is being set as root, unset any other root folders for the same product
            Folder.objects.filter(product=self.product, is_root=True).exclude(uuid=self.uuid).update(is_root=False)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name
    
    def delete(self, *args, **kwargs):
        # Delete all documents in the folder
        self.documents.all().delete()
        super().delete(*args, **kwargs)
    
    def is_descendant_of(self, potential_parent):
        """
        Determine if this folder is a descendant of another folder.
        """
        current_folder = self.parent
        while current_folder is not None:
            if current_folder.id == potential_parent:
                return True
            current_folder = current_folder.parent
        return False

    