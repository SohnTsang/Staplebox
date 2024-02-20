from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
import uuid

class Invitation(models.Model):
    sender = models.ForeignKey(User, related_name="sent_invitations", on_delete=models.CASCADE)
    email = models.EmailField()
    token = models.UUIDField(default=uuid.uuid4)
    accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invitation from {self.sender.email} to {self.email}"

    def get_acceptance_url(self):
        return reverse('invitations:accept_invitation', kwargs={'token': self.token})
