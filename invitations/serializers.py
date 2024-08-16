from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Invitation
from partners.models import Partnership
import logging
from django.db.models import Q
from companies.models import CompanyProfile

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
        user_company_profile = user.userprofile.company_profiles.first()

        if user_company_profile is None:
            logger.error("No company profile found for the user.")
            raise serializers.ValidationError("Please create a company profile to send invitations")

        if user_company_profile.email == value:
            logger.error("User attempted to send an invitation to their own company email.")
            raise serializers.ValidationError("You cannot send an invitation to yourself")

        # Check if the email belongs to an existing company profile
        try:
            recipient_company = CompanyProfile.objects.get(email=value)
        except CompanyProfile.DoesNotExist:
            # If no company profile is found with the email, check if the email belongs to a user with a company profile
            try:
                recipient_user = User.objects.get(email=value)
                recipient_company = recipient_user.userprofile.company_profiles.first()
                if not recipient_company:
                    raise serializers.ValidationError("No company found with this email address")
                # Convert to company profile email
                value = recipient_company.email
            except User.DoesNotExist:
                raise serializers.ValidationError("No company found with this email address")

        # Check if there is already an existing partnership
        if Partnership.objects.filter(
            (Q(partner1=user_company_profile) & Q(partner2=recipient_company)) | 
            (Q(partner2=user_company_profile) & Q(partner1=recipient_company)),
            is_active=True
        ).exists():
            logger.error("Partnership already exists with the company: %s", recipient_company)
            raise serializers.ValidationError("Partnership already exists with this company")

        return value

    def create(self, validated_data):
        logger.debug("Creating invitation with validated data: %s", validated_data)
        invitation = Invitation.objects.create(**validated_data)
        logger.info("Invitation created: %s", invitation)
        return invitation
