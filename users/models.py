from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.signing import Signer
from django.apps import apps
import uuid 
import logging
from django.db import IntegrityError

logger = logging.getLogger(__name__)

signer = Signer()

class UserProfile(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    company_profiles = models.ManyToManyField('companies.CompanyProfile', related_name='user_profiles')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.user.email

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.userprofile.save()


class UserActivity(models.Model):

    ACTIVITY_TYPE_CHOICES = [
        ('ACCOUNT_CREATION', 'Account Creation'),
        ('ACCESS_PERMISSION_GRANTED', 'Access Permission Granted'),
        ('ACCESS_PERMISSION_REVOKED', 'Access Permission Revoked'),
        ('COMMENT_UPDATE', 'Comment Update'),
        ('DOCUMENT_DOWNLOAD', 'Document Download'),
        ('DOCUMENT_UPDATE', 'Document Update'),
        ('DOCUMENT_UPLOAD', 'Document Upload'),
        ('EMAIL_CHANGE', 'Email Change'),
        ('EMAIL_PREFERENCE_UPDATE', 'Email Preferences Updated'),
        ('EXPORT_CREATION', 'Export Creation'),
        ('EXPORT_UPDATE', 'Export Update'),
        ('FEEDBACK_SUBMITTED', 'Feedback Submitted'),
        ('FOLDER_CREATION', 'Folder Creation'),
        ('FOLDER_UPDATE', 'Folder Update'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('NOTIFICATION_SETTING_UPDATE', 'Notification Settings Updated'),
        ('PARTNERSHIP_ACCEPT', 'Partnership Invite Accepted'),
        ('PARTNERSHIP_INVITE', 'Partnership Invite Sent'),
        ('PASSWORD_CHANGE', 'Password Change'),
        ('PRIVACY_SETTING_UPDATE', 'Privacy Settings Updated'),
        ('PRODUCT_CREATION', 'Product Creation'),
        ('PRODUCT_UPDATE', 'Product Update'),
        ('PROFILE_UPDATE', 'Profile Update'),
        ('SUPPORT_TICKET_CREATED', 'Support Ticket Created'),
        ('SUPPORT_TICKET_RESOLVED', 'Support Ticket Resolved'),
        ('TOKEN_USED', 'Company Token Used'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    action = models.CharField(max_length=255)
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPE_CHOICES)

    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.action} ({self.activity_type}) at {self.timestamp}"
