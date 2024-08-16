from django.db import models
from django.contrib.auth.models import User
from products.models import Product
from folder.models import Folder
from documents.models import Document
from django.core.cache import cache
import uuid
from django.core.signing import Signer
from companies.models import CompanyProfile

signer = Signer()

class AccessPermission(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)

    ACCESS_TYPES = [
        ('read_only', 'Read Only'),
        ('full', 'Full'),
    ]
    partner1 = models.ForeignKey(CompanyProfile, related_name='granted_permissions', on_delete=models.CASCADE)
    partner2 = models.ForeignKey(CompanyProfile, related_name='received_permissions', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, blank=True, null=True, on_delete=models.CASCADE)
    folder = models.ForeignKey(Folder, blank=True, null=True, on_delete=models.CASCADE)
    document = models.ForeignKey(Document, blank=True, null=True, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    access_type = models.CharField(max_length=50, choices=ACCESS_TYPES, default='full')

    
    def __str__(self):
        return f"{self.partner1} grants {self.partner2} - Prod: {self.product}, Folder: {self.folder}, Doc: {self.document}"

    def save(self, *args, **kwargs):
         
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ('partner1', 'partner2', 'product', 'folder', 'document')
        verbose_name_plural = "Access Permissions"

    @staticmethod
    def has_access_to_document(partner2, document):
        # Construct a unique cache key for this check
        cache_key = f"doc_access_{partner2.id}_{document.id}"
        
        # Try to get the result from cache
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        # If result is not in cache, perform the checks
        direct_permission = AccessPermission.objects.filter(partner2=partner2, document=document).exists()
        if direct_permission:
            cache.set(cache_key, True, 300)
        # Construct a unique cache key for this check
        cache_key = f"doc_access_{partner2.id}_{document.id}"
        
        # Try to get the result from cache
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        # If result is not in cache, perform the checks
        direct_permission = AccessPermission.objects.filter(partner2=partner2, document=document).exists()
        if direct_permission:
            cache.set(cache_key, True, 300)  # Cache this result for 5 minutes
            return True
        
        folder_permission = AccessPermission.objects.filter(partner2=partner2, folder=document.folder).exists()
        if folder_permission:
            cache.set(cache_key, True, 300)
            return True

        product_permission = AccessPermission.objects.filter(partner2=partner2, product=document.folder.product).exists()
        if product_permission:
            cache.set(cache_key, True, 300)
            return True

        # Cache the negative result to avoid repeated checks
        cache.set(cache_key, False, 300)
        return False

    def invalidate_permission_cache(partner2, document=None, folder=None, product=None):
        # You need to build logic to invalidate cache keys based on the arguments provided.
        # For simplicity, here's an example for document-level invalidation.
        if document:
            cache_key = f"doc_access_{partner2.id}_{document.id}"
            cache.delete(cache_key)