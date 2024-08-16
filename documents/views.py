from django.shortcuts import get_object_or_404, render
from .models import Document, DocumentVersion
from access_control.models import AccessPermission
from products.models import Product
from folder.models import Folder
from document_types.models import DocumentType
from django.views.decorators.csrf import csrf_exempt
from django.http import FileResponse
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
import os, hashlib
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.utils.html import escape  # Use escape to prevent XSS attacks
from django.utils.timezone import localtime
from folder.utils import handle_item_action, clean_bins
from partners.models import Partnership
from companies.models import CompanyProfile
from django.db.models import Q
from django.db import transaction
from .serializers import DocumentSerializer, DocumentCommentSerializer, DocumentVersionCommentSerializer, DocumentUpdateSerializer
from rest_framework.parsers import MultiPartParser
from rest_framework.decorators import api_view
import json
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import logging
from django.http import Http404
from rest_framework.parsers import MultiPartParser
from django.core.signing import Signer, BadSignature
from users.models import User

signer = Signer()

logger = logging.getLogger(__name__)

#For checking file integrity
def file_hash(file):
    hash_sha256 = hashlib.sha256()
    for chunk in file.chunks():
        hash_sha256.update(chunk)
    return hash_sha256.hexdigest()


class DocumentUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request, product_uuid, folder_uuid):
        logger.debug("Received upload request for product_uuid: %s, folder_uuid: %s", product_uuid, folder_uuid)

        try:
            unsigned_product_uuid = signer.unsign(product_uuid)
            logger.debug("Unsigned product_uuid: %s", unsigned_product_uuid)
            unsigned_folder_uuid = signer.unsign(folder_uuid)
            logger.debug("Unsigned folder_uuid: %s", unsigned_folder_uuid)
        except BadSignature:
            logger.warning("Invalid UUID signature for product_uuid: %s or folder_uuid: %s", product_uuid, folder_uuid)
            return Response({"detail": "Invalid UUID signature."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = get_object_or_404(Product, uuid=unsigned_product_uuid)
            folder = get_object_or_404(Folder, uuid=unsigned_folder_uuid, product__uuid=unsigned_product_uuid)
        except Product.DoesNotExist:
            logger.error("Product not found with uuid: %s", unsigned_product_uuid)
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)
        except Folder.DoesNotExist:
            logger.error("Folder not found with uuid: %s", unsigned_folder_uuid)
            return Response({"detail": "Folder not found."}, status=status.HTTP_404_NOT_FOUND)

        if product.user != request.user:
            logger.warning("Unauthorized access attempt by user: %s", request.user)
            return Response({"detail": "You are not authorized to perform this action."}, status=status.HTTP_403_FORBIDDEN)

        document_files = request.FILES.getlist('document_files')
        document_types = request.POST.getlist('document_types', [])
        comments = request.POST.getlist('comments', [])

        if not document_files:
            logger.error("No document files provided.")
            return Response({'detail': 'No document files provided.'}, status=status.HTTP_400_BAD_REQUEST)

        errors = []
        for i, file in enumerate(document_files):
            doc_type = document_types[i] if i < len(document_types) else None
            comment = comments[i] if i < len(comments) else ''
            data = {
                'folder': folder.uuid,
                'original_filename': file.name,
                'document_type': doc_type,
                'file': file,
                'uploaded_by': request.user.id,
                'comments': comment
            }
            logger.debug("Processing file: %s", file.name)
            serializer = DocumentSerializer(data=data)
            if not serializer.is_valid():
                errors.append({'file': file.name, 'errors': serializer.errors})

        if errors:
            logger.error("Errors encountered during upload: %s", errors)
            return Response({'detail': 'Error uploading documents.', 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        for i, file in enumerate(document_files):
            doc_type = document_types[i] if i < len(document_types) else None
            comment = comments[i] if i < len(comments) else ''
            data = {
                'folder': folder.uuid,
                'original_filename': file.name,
                'document_type': doc_type,
                'file': file,
                'uploaded_by': request.user.id,
                'comments': comment
            }
            serializer = DocumentSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                logger.debug("File uploaded successfully: %s", file.name)

        logger.info("All documents uploaded successfully for product_uuid: %s, folder_uuid: %s", product_uuid, folder_uuid)
        return Response({'detail': 'Documents uploaded'}, status=status.HTTP_201_CREATED)

    
class UploadDocumentPartnerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, folder_uuid):
        logger.debug("UploadDocumentPartnerView: Starting document upload process")
        try:
            unsigned_folder_uuid = signer.unsign(folder_uuid)
            logger.debug(f"Unsign successful: {unsigned_folder_uuid}")
        except BadSignature:
            logger.error("Invalid folder ID signature")
            return Response({'error': 'Invalid folder ID.'}, status=400)

        folder = get_object_or_404(Folder, uuid=unsigned_folder_uuid)
        partnership = get_object_or_404(Partnership, shared_folder=folder)

        # Get the company profile of the authenticated user
        user_profile = request.user.userprofile
        user_company_profile = user_profile.company_profiles.first()

        # Check if the user's company profile is part of the partnership
        if user_company_profile not in [partnership.partner1, partnership.partner2]:
            logger.error("User's company profile is not a partner in this partnership.")
            return Response({'error': 'You are not authorized to upload to this folder.'}, status=403)

        files = request.FILES.getlist('document_files')
        comments_list = request.POST.getlist('comments[]')
        logger.debug(f"Number of files: {len(files)}, Number of comments: {len(comments_list)}")

        if len(files) == 0:
            logger.error("No files received.")
            return Response({'error': 'No files received.'}, status=400)

        try:
            with transaction.atomic():
                documents = []
                for i, file in enumerate(files):
                    comment = comments_list[i] if i < len(comments_list) else ''  # Handle missing comments
                    logger.debug(f"Processing file: {file.name}, Comment: {comment}")
                    hasher = hashlib.sha256()
                    for chunk in file.chunks():
                        hasher.update(chunk)
                    file_hash = hasher.hexdigest()
                    logger.debug(f"File hash: {file_hash}")

                    document = Document.objects.create(
                        folder=folder,
                        original_filename=file.name,
                        file=file,
                        file_hash=file_hash,
                        uploaded_by=request.user,
                        comments=comment,
                    )
                    logger.debug(f"Document created: {document}")
                    documents.append(document)

                serializer = DocumentSerializer(documents, many=True)
                logger.debug("Documents uploaded successfully")
                return Response({'message': 'Documents uploaded', 'documents': serializer.data}, status=201)
        except Exception as e:
            logger.error(f"Failed to upload documents: {str(e)}")
            return Response({'error': f'Failed to upload documents. Error: {str(e)}'}, status=400)


def generate_new_filename(folder, original_filename):
    base_name, extension = os.path.splitext(original_filename)
    counter = 1

    # Generate a new file name with a counter if a file with the same name exists
    new_filename = f"{base_name} ({counter}){extension}"
    while Document.objects.filter(folder=folder, original_filename=new_filename).exists():
        counter += 1
        new_filename = f"{base_name} ({counter}){extension}"

    return new_filename


@login_required
@api_view(['POST'])
def edit_document(request, document_uuid):
    try:
        unsigned_document_uuid = signer.unsign(document_uuid)
    except BadSignature:
        return JsonResponse({'error': 'Invalid UUID'}, status=400)

    document = get_object_or_404(Document, uuid=unsigned_document_uuid)

    if request.method == 'POST':
        serializer = DocumentSerializer(data=request.data, instance=document)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse({'success': True, 'message': 'Document updated'})
        else:
            return JsonResponse({'success': False, 'errors': serializer.errors}, status=400)

    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)


@login_required
def ajax_get_document_details(request, document_uuid):
    try:
        unsigned_document_uuid = signer.unsign(document_uuid)
    except BadSignature:
        return JsonResponse({'error': 'Invalid UUID'}, status=400)

    document = get_object_or_404(Document, uuid=unsigned_document_uuid)
    document_types = DocumentType.objects.all().values('uuid', 'type_name')

    if document.versions.exists():
        latest_version = document.versions.latest('created_at')
        data = {
            'document_type_id': latest_version.document.document_type_id,
            'document_types': list(document_types),
            'original_filename': latest_version.original_filename,
            'comments': latest_version.comments,
        }
    else:
        data = {
            'document_type_id': document.document_type_id,
            'document_types': list(document_types),
            'original_filename': document.original_filename,
            'comments': document.comments,
        }

    return JsonResponse(data)


@login_required
def document_versions(request, document_id):
    original_document = get_object_or_404(Document, id=document_id)

    # Directly fetch versions related to the document from DocumentVersion model
    versions = DocumentVersion.objects.filter(document=original_document).order_by('-version')


    return render(request, 'documents/document_versions.html', {
        'original_document': original_document,
        'versions': versions
    })



@login_required
def ajax_document_versions(request, document_uuid):
    try:
        unsigned_document_uuid = signer.unsign(document_uuid)
    except BadSignature:
        return JsonResponse({'error': 'Invalid UUID'}, status=400)

    original_document = get_object_or_404(Document, uuid=unsigned_document_uuid)
    user = request.user

    is_owner = original_document.uploaded_by == user
    versions = DocumentVersion.objects.filter(document=original_document).order_by('-version')

    if not is_owner:
        versions = versions.filter(uploaded_by__in=[user, original_document.uploaded_by])

    versions_data = [{
        'version': version.version,
        'filename': version.original_filename,
        'modified': localtime(version.created_at).strftime("%Y-%m-%d %H:%M"),
        'uploader': version.uploaded_by.username,
        'download_url': reverse('documents:download_document', kwargs={'document_uuid': document_uuid, 'version_id': signer.sign(str(version.uuid))})
    } for version in versions]

    if not versions or (versions and versions.last().version != 1):
        versions_data.append({
            'version': 1,
            'filename': original_document.original_filename,
            'modified': localtime(original_document.created_at).strftime("%Y-%m-%d %H:%M"),
            'uploader': original_document.uploaded_by.username,
            'download_url': reverse('documents:download_document', kwargs={'document_uuid': document_uuid})
        })

    data = {
        'is_owner': is_owner,
        'original_filename': original_document.original_filename,
        'versions': versions_data
    }
    return JsonResponse(data)


class UpdateDocument(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, document_uuid):
        try:
            unsigned_document_uuid = signer.unsign(document_uuid)
        except BadSignature:
            return Response({"detail": "Invalid document ID."}, status=status.HTTP_400_BAD_REQUEST)

        document = get_object_or_404(Document, uuid=unsigned_document_uuid)
        user = request.user

        # Check if the user is the owner or has access
        is_owner = document.uploaded_by == user
        has_access = AccessPermission.objects.filter(partner2=user, document=document).exists()

        if not (is_owner or has_access):
            return Response({"detail": "You do not have permission to update this document."}, status=status.HTTP_403_FORBIDDEN)

        serializer = DocumentUpdateSerializer(document, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Document updated'}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@login_required
@require_POST  # Ensure this view only accepts POST requests
def ajax_update_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    user = request.user

    # Permission checks
    is_owner = document.uploaded_by == user
    has_access = AccessPermission.objects.filter(partner2=user, document=document).exists()

    if not (is_owner or has_access):
        return JsonResponse({'error': 'You do not have permission to update this document'}, status=403)

    uploaded_file = request.FILES.get('file')
    comments = request.POST.get('comments')

    if uploaded_file:
        new_hash = file_hash(uploaded_file)  # Your file_hash function needs to be defined
        document.update_version(uploaded_file, new_hash, comments, user)

        return JsonResponse({'message': 'Document updated'})

    return JsonResponse({'error': 'No file was uploaded'}, status=400)


class DeleteDocumentView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        signed_document_ids = request.data.get('document_ids', [])
        document_ids = []

        # Unsign the UUIDs
        for signed_id in signed_document_ids:
            try:
                unsigned_id = signer.unsign(signed_id)
                document_ids.append(unsigned_id)
            except BadSignature:
                return Response({"detail": "Invalid document ID."}, status=status.HTTP_400_BAD_REQUEST)

        documents = Document.objects.filter(uuid__in=document_ids)

        if not documents.exists():
            return Response({"detail": "Documents not found."}, status=status.HTTP_404_NOT_FOUND)

        for document in documents:
            if document.folder.product.user != request.user:
                return Response({"detail": "You do not have permission to delete this document."}, status=status.HTTP_403_FORBIDDEN)

            document.versions.all().delete()
            document.delete()

        return Response({'detail': 'Items deleted'}, status=status.HTTP_200_OK)


class DeletePartnerDocumentView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, document_uuid):
        try:
            # Unsign the document UUID
            unsigned_document_uuid = signer.unsign(document_uuid)
        except BadSignature:
            return Response({"detail": "Invalid document ID."}, status=400)

        document = get_object_or_404(Document, uuid=unsigned_document_uuid)

        # Check if the user is in a partnership with the document's owner
        if request.user != document.uploaded_by:
            return Response({"detail": "You do not have permission to delete this document."}, status=403)

        # Delete the document and all its versions
        document.versions.all().delete()
        document.delete()

        return Response({'detail': 'Document deleted'}, status=200)
    
    
@login_required
def move_to_bin_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    parent_id = document.folder.uuid
    bin_folder = Folder.objects.get_or_create(name="Bin", product=document.folder.product, is_bin=True)[0]
    handle_item_action("move_to_bin", document, bin_folder=bin_folder)
    clean_bins()
    return redirect('products:product_explorer_folder', product_uuid=document.folder.product.uuid, folder_id=parent_id)


@login_required
def restore_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    handle_item_action("restore", document)
    return redirect('products:product_explorer_bin', product_uuid=document.folder.product.uuid)


@login_required
def download_document(request, document_uuid, version_id=None):
    try:
        unsigned_document_uuid = signer.unsign(document_uuid)
    except BadSignature:
        raise Http404("Invalid document UUID")

    if version_id:
        version = get_object_or_404(DocumentVersion, version=version_id, document__uuid=unsigned_document_uuid)
        file_path = version.file.path
        document = version.document
        download_filename = f"{version.original_filename.split('.')[0]}.{version.original_filename.split('.')[-1]}"
    else:
        document = get_object_or_404(Document, uuid=unsigned_document_uuid)
        file_path = document.file.path
        original_filename = document.original_filename
        file_name, file_extension = os.path.splitext(original_filename)
        download_filename = f"{file_name}{file_extension}"

    current_hash = file_hash(document.file)

    # Verify integrity
    if current_hash != document.file_hash:
        raise ValueError("File integrity check failed.")

    response = FileResponse(open(file_path, 'rb'))
    response['Content-Disposition'] = f'attachment; filename="{download_filename}"'
    return response


def get_documents(request, product_id, folder_id):
    documents = Document.objects.filter(folder_id=folder_id)
    documents_data = [{
        'id': doc.id,
        'name': doc.file_name,
        'size': doc.file_size,
        'type': doc.file_type,
        'uploaded_at': doc.formatted_upload_date,
        'document_type': doc.document_type.type_name
    } for doc in documents]
    return JsonResponse({'documents': documents_data})


@login_required
def comment_versions(request, document_uuid):
    try:
        unsigned_document_uuid = signer.unsign(document_uuid)
    except BadSignature:
        return JsonResponse({'error': 'Invalid UUID'}, status=400)

    original_document = get_object_or_404(Document, uuid=unsigned_document_uuid)
    versions = DocumentVersion.objects.filter(document=original_document).order_by('-version')
    return render(request, 'documents/comment_versions.html', {
        'original_document': original_document,
        'versions': versions
    })


@login_required
def ajax_comments_versions(request, document_uuid):
    try:
        unsigned_document_uuid = signer.unsign(document_uuid)
    except BadSignature:
        return JsonResponse({'error': 'Invalid UUID'}, status=400)

    document = get_object_or_404(Document, uuid=unsigned_document_uuid)
    user = request.user

    is_owner = document.uploaded_by == user
    versions = DocumentVersion.objects.filter(document=document).order_by('-version')

    if not is_owner:
        versions = versions.filter(uploaded_by__in=[user, document.uploaded_by])
    
    versions_data = [{
        'id': signer.sign(str(version.uuid)),
        'version': version.version,
        'comment': version.comments or "No comment",
        'is_editable': version.uploaded_by == user or is_owner,
        'modified': localtime(version.updated_at).strftime("%Y-%m-%d %H:%M"),
        'uploader': version.uploaded_by.username,
    } for version in versions]

    if not versions or (versions and versions.last().version != 1):
        versions_data.append({
            'id': document.uuid,
            'version': 1,
            'comment': document.comments or "No initial comment",
            'is_editable': is_owner,
            'modified': localtime(document.updated_at).strftime("%Y-%m-%d %H:%M"),
            'uploader': document.uploaded_by.username,
        })

    return JsonResponse({
        'is_owner': is_owner,
        'versions': versions_data
    })


class EditComment(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, document_uuid, version_number=None):
        try:
            unsigned_document_uuid = signer.unsign(document_uuid)
        except BadSignature:
            return Response({'error': 'Invalid UUID'}, status=status.HTTP_400_BAD_REQUEST)

        logger.debug(f"Received request for document_uuid: {unsigned_document_uuid} with version_number: {version_number}")

        if version_number is not None:
            if version_number == 1:
                instance = get_object_or_404(Document, uuid=unsigned_document_uuid)
                serializer_class = DocumentCommentSerializer
            else:
                instance = get_object_or_404(DocumentVersion, document__uuid=unsigned_document_uuid, version=version_number)
                serializer_class = DocumentVersionCommentSerializer
            logger.debug(f"Editing version instance: {instance}")
        else:
            instance = get_object_or_404(Document, uuid=unsigned_document_uuid)
            logger.debug(f"Editing document instance: {instance}")
            serializer_class = DocumentCommentSerializer

        logger.debug(f"Request data: {request.data}")
        serializer = serializer_class(instance, data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.debug(f"Comment updated successfully for instance: {instance}")
            logger.debug(f"Updated instance data: {serializer.data}")
            return Response({
                'success': True,
                'message': 'Comment updated',
                'modified': instance.formatted_modified_date
            })
        else:
            logger.error(f"Serializer errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



def user_has_access(user, document):
    # Check if the user is the uploader of the document
    # Assuming your Document model has a field linking to the uploader (adjust as necessary)
    if document.uploaded_by == user:
        return True

    # Adjust the logic below based on your model's relationships and fields
    # If the document is associated with a folder, and that folder with a product
    if hasattr(document, 'folder') and document.folder and hasattr(document.folder, 'product'):
        product = document.folder.product
    # Direct association with a product (if applicable)
    elif hasattr(document, 'product') and document.product:
        product = document.product
    else:
        product = None

    if product:
        # For example, if AccessPermission links users to products they can access
        if AccessPermission.objects.filter(importer=user, product=product).exists():
            return True

    # If no conditions are met, the user does not have access
    return False