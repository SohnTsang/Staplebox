from django.db import models
import uuid, secrets, hashlib, os
from django.core.signing import Signer

signer = Signer()


def company_profile_image_upload_to(instance, filename):
    """
    Generate the upload path for a company profile image.
    Path format: company_<uuid>/profile/<filename>
    """
    return os.path.join(
        f"company_{str(instance.uuid)}",  # Use company UUID
        'profile',
        filename
    )


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
        related_name='company_profiles'
    )

    invite_token = models.CharField(max_length=255, unique=True, null=True, blank=True)
    token_uses = models.IntegerField(default=0)
    max_token_uses = models.IntegerField(default=2)  # Set the limit here

    # Contact Information
    primary_contact_name = models.CharField(max_length=255, null=True, blank=True)
    primary_contact_email = models.EmailField(null=True, blank=True)

    # Social Media Links
    linkedin = models.URLField(max_length=200, null=True, blank=True)
    facebook = models.URLField(max_length=200, null=True, blank=True)
    twitter = models.URLField(max_length=200, null=True, blank=True)

    profile_image = models.ImageField(upload_to=company_profile_image_upload_to, null=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.invite_token:
            self.invite_token = self.generate_unique_token()
        super().save(*args, **kwargs)

    def generate_unique_token(self):
        # Generate a UUID
        base_token = str(uuid.uuid4())

        # Add additional randomness
        random_data = secrets.token_hex(16)

        # Combine the UUID and random data
        combined_data = base_token + random_data

        # Hash the combined data
        hashed_token = hashlib.sha256(combined_data.encode()).hexdigest()

        # Sign the hashed token
        signed_token = signer.sign(hashed_token)

        return signed_token

    def can_use_token(self):
        return self.token_uses < self.max_token_uses

    def use_token(self):
        if self.can_use_token():
            self.token_uses += 1
            self.save()
            return True
        return False