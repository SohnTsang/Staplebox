from django.db import models
from django.utils import timezone
import uuid
from django.core.signing import Signer

signer = Signer()

class DocumentType(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
     

    type_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.type_name
    
    def save(self, *args, **kwargs):
         
        super().save(*args, **kwargs)