from django.db import models
from django.contrib.auth.models import User

class Partnership(models.Model):
    exporter = models.ForeignKey(User, related_name='exporter_partnerships', on_delete=models.CASCADE)
    importer = models.ForeignKey(User, related_name='importer_partnerships', on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.exporter} - {self.importer}"

    class Meta:
        unique_together = ('exporter', 'importer')  # Ensure unique partnerships