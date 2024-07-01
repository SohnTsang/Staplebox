from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Invitation
from partners.models import Partnership
import logging
from django.db.models import Q

logger = logging.getLogger(__name__)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class InvitationSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M', read_only=True)

    class Meta:
        model = Invitation
        fields = ['id', 'sender', 'email', 'token', 'accepted', 'created_at']
        read_only_fields = ['id', 'sender', 'token', 'accepted', 'created_at']

    def validate_email(self, value):
        logger.debug("Validating email: %s", value)
        request = self.context.get('request')
        user = request.user

        if user.email == value:
            raise serializers.ValidationError("You cannot send an invitation to yourself")

        # Check if the email belongs to an existing user
        try:
            recipient = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("No user found with this email address")

        # Check if there is already an existing partnership
        if Partnership.objects.filter(
            (Q(partner1=user) & Q(partner2=recipient)) | 
            (Q(partner2=user) & Q(partner1=recipient)),
            is_active=True
        ).exists():
            raise serializers.ValidationError("Partnership already exists with this user")

        return value

    def create(self, validated_data):
        logger.debug("Creating invitation with validated data: %s", validated_data)
        request = self.context['request']
        invitation = Invitation.objects.create(
            **validated_data,
            sender=request.user
        )
        return invitation
