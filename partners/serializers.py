from rest_framework import serializers
from partners.models import Partnership
from companies.models import CompanyProfile
from invitations.models import Invitation
from django.contrib.auth.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['email']

class PartnershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partnership
        fields = '__all__'

class CompanyProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyProfile
        fields = '__all__'

class InvitationSerializer(serializers.ModelSerializer):
    sender = UserSerializer()

    class Meta:
        model = Invitation
        fields = '__all__'


class PartnerSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = Partnership
        fields = ['uuid', 'name']

    def get_name(self, obj):
        # Check if request is available in context
        request_user = self.context.get('request').user
        try:
            if obj.partner1.user_profiles.filter(user=request_user).exists():
                return obj.partner2.name
            else:
                return obj.partner1.name
        except AttributeError as e:
            return str(e)  # Return the error message or handle it as you see fit


