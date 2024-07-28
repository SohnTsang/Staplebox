from django.db import models
from django.contrib.auth.models import User
from users.models import UserProfile  # Assuming your UserProfile model is in users/models.py
from django.apps import apps
from django.db import transaction
import uuid
from django.core.signing import Signer, BadSignature

signer = Signer()

class CompanyProfile(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=[
        ('trading', 'Trading'),
        ('wholesaler', 'Wholesaler'),
        ('retailer', 'Retailer'),
        ('food service', 'Food Service'),
        ('manufacturer', 'Manufacturer'),
        ('logistics', 'Logistics'),
        ('financial services', 'Financial services'),
        ('insurance', 'Insurance'),
        ('government agency', 'Government Agency'),
        ('other', 'Other'),
    ], blank=True, null=True)
    address = models.TextField()
    phone_number = models.CharField(max_length=20)
    email = models.EmailField()
    website = models.URLField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    partners_contract_folder = models.ForeignKey(
        'folder.Folder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        with transaction.atomic():
            is_new = self._state.adding
            super().save(*args, **kwargs)
            if is_new:
                Folder = apps.get_model('folder', 'Folder')
                folder = Folder.objects.create(name=f"{self.name} Contracts", description="Storage for partners' contracts.")
                self.partners_contract_folder = folder
            super().save(*args, **kwargs)