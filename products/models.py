from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps
import uuid
from django.core.signing import Signer
from companies.models import CompanyProfile

signer = Signer()

class Product(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
       # This field will be set in the save method

    PRODUCT_TYPES = [
        ('meat_products', 'Meat Products'),
        ('poultry_products', 'Poultry Products'),
        ('egg_products', 'Egg Products'),
        ('seafood', 'Seafood'),
        ('dairy_products', 'Dairy Products'),
        ('fruits_vegetables', 'Fruits and Vegetables'),
        ('grains_cereals', 'Grains and Cereals'),
        ('processed_foods', 'Processed Foods'),
    ]
    company = models.ForeignKey(CompanyProfile, on_delete=models.CASCADE, related_name='products')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    product_code = models.CharField(max_length=50)
    product_name = models.CharField(max_length=100)
    product_description = models.TextField(blank=True, null=True, max_length=100)
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES)  # New field
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'product_code')

    def save(self, *args, **kwargs):
        self.product_code = self.product_code.upper()  # Ensure product_code is uppercase
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            Folder = apps.get_model('folder', 'Folder')  # Replace 'app_name' with the name of your app
            Folder.objects.create(name="Root", product=self, parent=None)
            Folder.objects.create(name="Bin", product=self, parent=None, is_bin=True)

    def __str__(self):
        return self.product_name
    
    