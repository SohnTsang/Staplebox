from django.db import models
from django.utils import timezone
from products.models import Product
from document_types.models import DocumentType
import uuid
from django.core.signing import Signer

signer = Signer()

class ComplianceRequirement(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)

    product = models.ForeignKey(Product, on_delete=models.CASCADE,
                related_name='compliance_requirements')
    document_type = models.ForeignKey(DocumentType, on_delete=models.CASCADE)
    country_code = models.CharField(max_length=2) # ISO 3166-1 alpha-2 country codes
    is_required = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)