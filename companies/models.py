from django.db import models
from django.contrib.auth.models import User
from users.models import UserProfile  # Assuming your UserProfile model is in users/models.py
from django.apps import apps
from django.db import transaction

class CompanyProfile(models.Model):
    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    ROLE_CHOICES = [
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
        ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True, null=True)
    address = models.TextField()
    phone_number = models.CharField(max_length=20)
    email = models.EmailField()
    website = models.URLField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    partners_contract_folder = models.ForeignKey('folder.Folder', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')


    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        with transaction.atomic():
            is_new = self._state.adding
            if is_new:
                super().save(*args, **kwargs)  # Save first to ensure it has an ID if needed
                Folder = apps.get_model('folder', 'Folder')
                folder = Folder.objects.create(name=f"{self.name} Contracts", description="Storage for partners' contracts.")
                self.partners_contract_folder = folder
            super().save(*args, **kwargs)  # Save again to record the folder 