from rest_framework import serializers
from folder.models import Folder
from .models import Product

class MoveEntitiesSerializer(serializers.Serializer):
    entity_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True)
    entity_types = serializers.ListField(child=serializers.CharField(), write_only=True)
    target_folder_id = serializers.IntegerField(write_only=True)

    def validate(self, data):
        # Check that the lengths of entity_ids and entity_types are the same
        if len(data['entity_ids']) != len(data['entity_types']):
            raise serializers.ValidationError("Mismatch between entity IDs and types.")

        # Validate that the target folder exists
        target_folder = Folder.objects.filter(pk=data['target_folder_id']).first()
        if not target_folder:
            raise serializers.ValidationError({"target_folder_id": "Target folder does not exist."})
        data['target_folder'] = target_folder

        # Check for invalid movements, such as moving a folder into itself or into its direct child, which could cause infinite loops or hierarchy issues
        for entity_id, entity_type in zip(data['entity_ids'], data['entity_types']):
            if entity_type == 'folder' and entity_id == data['target_folder_id']:
                raise serializers.ValidationError(f"Cannot move folder {entity_id} into itself.")
            
            if entity_type == 'folder':
                # Prevent a folder from being moved into one of its descendants, which would cause a recursive loop
                if self._is_descendant_of(entity_id, data['target_folder_id']):
                    raise serializers.ValidationError(f"Cannot move folder {entity_id} into one of its descendants.")

        return data

    def _is_descendant_of(self, folder_id, potential_parent_id):
        # Recursive function to check if folder_id is a descendant of potential_parent_id
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
