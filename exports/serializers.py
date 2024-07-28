from rest_framework import serializers
from .models import Export
from documents.models import Document
import logging
import hashlib
from partners.serializers import PartnerSerializer

logger = logging.getLogger(__name__)


class DocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(use_url=False)

    class Meta:
        model = Document
        fields = ['file', 'uploaded_by', 'folder', 'original_filename', 'created_at', 'comments', 'file_hash']

    def create(self, validated_data):
        file = validated_data.pop('file')
        validated_data['original_filename'] = file.name  # Ensure the original filename is set

        # Compute the file hash
        hash_sha256 = hashlib.sha256()
        for chunk in file.chunks():
            hash_sha256.update(chunk)
        validated_data['file_hash'] = hash_sha256.hexdigest()  # Set the computed hash

        logger.info(f"Creating document with data: {validated_data}")
        document = Document.objects.create(file=file, **validated_data)
        logger.info(f"Document created with ID {document.uuid}")
        return document

class ExportSerializer(serializers.ModelSerializer):
    documents = DocumentSerializer(many=True, required=False)
    partner = PartnerSerializer(read_only=True)  # If partner needs to be updated, create a method to handle it

    class Meta:
        model = Export
        fields = ['uuid', 'reference_number', 'label', 'export_date', 'created_by', 'partner', 'folder', 'documents', 'products']
        read_only_fields = ['created_by']

    def create(self, validated_data):
        logger.info(f"Creating export with data: {validated_data}")
        documents_data = validated_data.pop('documents', [])
        products_data = validated_data.pop('products', [])

        export = Export.objects.create(**validated_data)
        logger.info(f"Created export with ID {export.uuid}")

        if products_data:
            export.products.set(products_data)

        for doc_data in documents_data:
            logger.info(f"Processing document: {doc_data}")
            doc_data['uploaded_by'] = doc_data['uploaded_by'] if isinstance(doc_data['uploaded_by'], int) else doc_data['uploaded_by'].pk
            doc_data['folder'] = doc_data['folder'] if isinstance(doc_data['folder'], int) else doc_data['folder'].pk
            doc_serializer = DocumentSerializer(data=doc_data, context=self.context)
            if doc_serializer.is_valid():
                logger.info("Document serializer is valid")
                document = doc_serializer.save()
                export.documents.add(document)
                logger.info(f"Added document with ID {document.uuid} to export {export.uuid}")
            else:
                logger.error(f"Document serializer errors: {doc_serializer.errors}")
                raise serializers.ValidationError(doc_serializer.errors)

        return export

    def update(self, instance, validated_data):
        instance.reference_number = validated_data.get('reference_number', instance.reference_number)
        instance.label = validated_data.get('label', instance.label)
        instance.export_date = validated_data.get('export_date', instance.export_date)

        partner_data = validated_data.get('partner')
        if partner_data:
            partner_id = partner_data.get('id')
            instance.partner_id = partner_id

        instance.save()
        logger.debug(f"Export updated successfully with instance: {instance}")
        return instance
