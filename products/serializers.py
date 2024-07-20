from rest_framework import serializers
from folder.models import Folder
from .models import Product
import logging

logger = logging.getLogger(__name__)


class MoveEntitiesSerializer(serializers.Serializer):
    entity_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True)
    entity_types = serializers.ListField(child=serializers.CharField(), write_only=True)
    target_folder_id = serializers.IntegerField(write_only=True)

    def validate(self, data):
        target_folder = Folder.objects.filter(pk=data['target_folder_id']).first()
        if not target_folder:
            raise serializers.ValidationError({"target_folder_id": "Target folder does not exist."})
        data['target_folder'] = target_folder

        for entity_id, entity_type in zip(data['entity_ids'], data['entity_types']):
            if entity_type == 'folder':
                if entity_id == data['target_folder_id']:
                    raise serializers.ValidationError("Cannot move a folder into itself")

                if Folder.objects.filter(pk=entity_id, parent=data['target_folder_id']).exists():
                    # Direct child check: Prevent moving to direct child
                    raise serializers.ValidationError(f"Cannot move folder to its direct child")

                if self._is_descendant_of(data['target_folder_id'], entity_id):
                    # Descendant check: Ensure we're not moving to a descendant
                    raise serializers.ValidationError(f"Cannot move folder into one of its descendants")

        return data

    def _is_descendant_of(self, folder_id, potential_parent_id):
        """
        Check if the folder with `folder_id` is a descendant of `potential_parent_id`.
        This function returns True only if `folder_id` is a child or further descendant (not parent or same-level) of `potential_parent_id`.
        """
        current_folder = Folder.objects.get(pk=folder_id)
        while current_folder.parent:
            if current_folder.parent_id == potential_parent_id:
                return True
            current_folder = current_folder.parent
        return False


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'product_code', 'product_name', 'product_description', 'product_type', 'created_at', 'updated_at']
        extra_kwargs = {
            'product_name': {
                'error_messages': {
                    'blank': 'This field is required.',  # Custom message for blank field
                    'required': 'This field is required.'  # Custom message if field is missing
                }
            },
            'product_code': {
                'error_messages': {
                    'blank': 'This field is required.',
                    'required': 'This field is required.'
                }
            },
            'product_description': {
                'error_messages': {
                    'blank': 'This field is required.',
                    'required': 'This field is required.'
                }
            },
            'product_type': {
                'error_messages': {
                    'blank': 'This field is required.',
                    'required': 'This field is required.'
                }
            }
        }
