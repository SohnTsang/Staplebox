# serializers.py
from rest_framework import serializers
from .models import Product, Folder, Document, AccessPermission
from django.contrib.auth.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'

class FolderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Folder
        fields = '__all__'

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = '__all__'

class AccessPermissionSerializer(serializers.ModelSerializer):
    partner1 = UserSerializer()
    partner2 = UserSerializer()
    product = ProductSerializer()
    folder = FolderSerializer()
    document = DocumentSerializer()

    class Meta:
        model = AccessPermission
        fields = ['partner1', 'partner2', 'product', 'folder', 'document', 'access_type', 'created_at']

