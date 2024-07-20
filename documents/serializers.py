from rest_framework import serializers
from .models import Document, DocumentVersion
import hashlib, logging, os
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class DocumentSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Document
        fields = ['folder', 'original_filename', 'document_type', 'file', 'uploaded_by', 'comments', 'file_hash', 'version']

    def __init__(self, *args, **kwargs):
        super(DocumentSerializer, self).__init__(*args, **kwargs)
        if self.instance is not None:  # if it's an update operation
            self.fields['folder'].required = False
            self.fields['file'].required = False
            self.fields['uploaded_by'].required = False
            
        
    def create(self, validated_data):
        logger.debug("Create method called")
        try:
            folder = validated_data['folder']
            original_filename = validated_data['original_filename']
            file = validated_data['file']
            uploaded_by = validated_data['uploaded_by']
            comments = validated_data.get('comments', '')

            # Calculate file hash
            hasher = hashlib.sha256()
            for chunk in file.chunks():
                hasher.update(chunk)
            file_hash = hasher.hexdigest()

            # Check for existing documents with the same name
            existing_count = Document.objects.filter(
                folder=folder,
                original_filename__startswith=original_filename.rsplit('.', 1)[0]
            ).count()

            if existing_count > 1:
                name, ext = os.path.splitext(original_filename)
                new_filename = f"{name} ({existing_count}){ext}"
            else:
                new_filename = original_filename

            new_document = Document.objects.create(
                folder=folder,
                original_filename=new_filename,
                document_type=validated_data.get('document_type'),
                file=file,
                file_hash=file_hash,
                uploaded_by=uploaded_by,
                comments=comments,
                version=1
            )
            return new_document
        except Exception as e:
            logger.error(f"Error creating document: {str(e)}")
            raise ValidationError(f"Error creating document: {str(e)}")
    
    
    def update(self, instance, validated_data):
        print("Update method called")
        # Assign the validated data to the instance
        instance.folder = validated_data.get('folder', instance.folder)
        instance.original_filename = validated_data.get('original_filename', instance.original_filename)
        instance.document_type = validated_data.get('document_type', instance.document_type)
        instance.comments = validated_data.get('comments', instance.comments)
        instance.uploaded_by = validated_data.get('uploaded_by', instance.uploaded_by)

        # Handle file update if a new file is provided
        file = validated_data.get('file')
        if file is not None:
            hasher = hashlib.sha256()
            for chunk in file.chunks():
                hasher.update(chunk)
            instance.file_hash = hasher.hexdigest()
            instance.file = file

        # Save the instance
        instance.save()
        return instance
    

class DocumentCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['comments']

    def update(self, instance, validated_data):
        new_comment = validated_data.get('comments', instance.comments)
        logger.debug(f"Received new comment: {new_comment}")
        instance.comments = new_comment
        instance.save(update_fields=['comments'])
        logger.debug(f"Updated comments: {instance.comments}")
        return instance
    

class DocumentVersionCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentVersion
        fields = ['comments']

    def update(self, instance, validated_data):
        new_comment = validated_data.get('comments', instance.comments)
        logger.debug(f"Received new comment: {new_comment}")
        instance.comments = new_comment
        instance.save(update_fields=['comments'])
        logger.debug(f"Updated comments: {instance.comments}")
        return instance
    

class DocumentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['file', 'comments']  # Only include fields that need to be updated

    def update(self, instance, validated_data):
        # Handling file update
        file = validated_data.get('file', None)
        if file:
            # Compute file hash if file is updated
            hasher = hashlib.sha256()
            for chunk in file.chunks():
                hasher.update(chunk)
            file_hash = hasher.hexdigest()

            # Check if it's truly a new version by comparing hashes
            if file_hash != instance.file_hash:
                instance.file_hash = file_hash  # Updating the file hash
                instance.file = file  # Updating the file itself
                # Update the version number
                instance.version += 1
                instance.save()

                # Optionally, create a new DocumentVersion entry
                DocumentVersion.objects.create(
                    document=instance,
                    file=instance.file,
                    version=instance.version,
                    uploaded_by=self.context['request'].user,
                    original_filename=file.name,
                    file_hash=file_hash,
                    comments=validated_data.get('comments', instance.comments)
                )

        # Update comments if provided and file hasn't changed
        if 'comments' in validated_data and not file:
            instance.comments = validated_data.get('comments', instance.comments)
            instance.save()

        return instance