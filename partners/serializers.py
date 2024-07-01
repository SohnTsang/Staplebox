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
        fields = ['id', 'name']

    def get_name(self, obj):
        # Check if request is available in context
        request_user = self.context.get('request', None)
        if request_user:
            request_user = request_user.user
        else:
            # Fallback to some default behavior or handle it as needed
            return 'Unknown Partner'

        try:
            if obj.partner1 == request_user:
                # Assuming you have a related_name `userprofile` for User to UserProfile linkage
                return obj.partner2.userprofile.companyprofile.name if hasattr(obj.partner2, 'userprofile') else 'No Company Profile'
            else:
                return obj.partner1.userprofile.companyprofile.name if hasattr(obj.partner1, 'userprofile') else 'No Company Profile'
        except AttributeError as e:
            return str(e)  # Return the error message or handle it as you see fit


