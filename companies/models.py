from django.db import models
from django.contrib.auth.models import User
from users.models import UserProfile  # Assuming your UserProfile model is in users/models.py

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

    def __str__(self):
        return self.name