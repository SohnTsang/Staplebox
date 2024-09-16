# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Folder, Document, AccessPermission

@receiver(post_save, sender=Folder)
def auto_grant_access_on_folder_creation(sender, instance, created, **kwargs):
    if created and instance.parent:
        parent_permissions = AccessPermission.objects.filter(folder=instance.parent, is_direct=True)
        for permission in parent_permissions:
            AccessPermission.objects.get_or_create(
                partner1=permission.partner1,
                partner2=permission.partner2,
                product=instance.product,
                folder=instance,
                defaults={'is_direct': True}
            )

@receiver(post_save, sender=Document)
def auto_grant_access_on_document_creation(sender, instance, created, **kwargs):
    if created and instance.folder:
        parent_permissions = AccessPermission.objects.filter(folder=instance.folder, is_direct=True)
        for permission in parent_permissions:
            AccessPermission.objects.get_or_create(
                partner1=permission.partner1,
                partner2=permission.partner2,
                product=instance.folder.product,
                document=instance,
                defaults={'is_direct': True}
            )
