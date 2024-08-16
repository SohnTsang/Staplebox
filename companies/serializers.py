from rest_framework import serializers
from .models import CompanyProfile

class CompanyProfileSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format=None)

    class Meta:
        model = CompanyProfile
        fields = '__all__'

    def validate_name(self, value):
        if CompanyProfile.objects.exclude(id=self.instance.id if self.instance else None).filter(name=value).exists():
            raise serializers.ValidationError("A company with this name already exists.")
        return value
