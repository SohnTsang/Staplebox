from django.db import models
from django.contrib.auth.models import User

class Partnership(models.Model):
    #exporter = models.ForeignKey(User, related_name='exporter_partnerships', on_delete=models.CASCADE)
    #importer = models.ForeignKey(User, related_name='importer_partnerships', on_delete=models.CASCADE)
    partner1 = models.ForeignKey(User, related_name='partnership_as_partner1', on_delete=models.CASCADE)
    partner2 = models.ForeignKey(User, related_name='partnership_as_partner2', on_delete=models.CASCADE)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.partner1} - {self.partner2}"

    class Meta:
        # Evaluate if unique_together is needed based on your application logic
        # It may still be useful if you want to prevent duplicate partnerships between the same two users
        unique_together = ('partner1', 'partner2')
