from rest_framework import serializers
from .models import UserProfile
from companies.models import CompanyProfile

class CompanyProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyProfile
        fields = ['name', 'role']

class UserProfileSerializer(serializers.ModelSerializer):
    company_profiles = CompanyProfileSerializer(many=True, read_only=True)

    class Meta:
        model = UserProfile
        fields = ['uuid', 'user', 'company_profiles', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']