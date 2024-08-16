from django.db import models
from django.contrib.auth.models import User
import uuid
from django.core.signing import Signer
from django.apps import apps
import logging

logger = logging.getLogger(__name__)

signer = Signer()


class Partnership(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    partner1 = models.ForeignKey('companies.CompanyProfile', related_name='partnership_as_partner1', on_delete=models.CASCADE)
    partner2 = models.ForeignKey('companies.CompanyProfile', related_name='partnership_as_partner2', on_delete=models.CASCADE)
    shared_folder = models.ForeignKey('folder.Folder', on_delete=models.SET_NULL, null=True, blank=True, related_name='partnerships')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.partner1.name} - {self.partner2.name}"

    class Meta:
        unique_together = ('partner1', 'partner2')

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            self.ensure_shared_folder()

    def ensure_shared_folder(self):
        if not self.shared_folder:
            logger.debug("Creating a new shared folder")
            Folder = apps.get_model('folder', 'Folder')
            shared_folder = Folder.objects.create(
                name=f"Shared Folder {self.partner1.name} & {self.partner2.name}",
                description="Shared folder for partnership."
            )
            self.shared_folder = shared_folder
            self.save()
            logger.debug(f"Shared folder created: {self.shared_folder}")

        self.update_partner_profiles()

    def update_partner_profiles(self):
        logger.debug("Updating partner profiles with shared folder")
        self.partner1.partners_contract_folder = self.shared_folder
        self.partner1.save()
        logger.debug(f"Updated CompanyProfile for partner1: {self.partner1}")

        self.partner2.partners_contract_folder = self.shared_folder
        self.partner2.save()
        logger.debug(f"Updated CompanyProfile for partner2: {self.partner2}")