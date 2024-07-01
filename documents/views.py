from django.shortcuts import get_object_or_404, render
from .models import Document, DocumentVersion
from access_control.models import AccessPermission
from products.models import Product
from folder.models import Folder
from document_types.models import DocumentType
from django.views.decorators.csrf import csrf_exempt
from django.http import FileResponse
from django.http import JsonResponse, HttpResponseNotAllowed
from django.http import HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
import os, hashlib
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.http import HttpResponseForbidden
from django.utils.html import escape  # Use escape to prevent XSS attacks
from .forms import DocumentEditForm  # Assuming you will create this form
from django.utils import timezone 
from django.utils.timezone import localtime
from folder.utils import handle_item_action, clean_bins
from partners.models import Partnership
from companies.models import CompanyProfile
from django.db.models import Q
from django.db import transaction
from rest_framework.parsers import JSONParser
from .serializers import DocumentSerializer, DocumentCommentSerializer, DocumentVersionCommentSerializer, DocumentUpdateSerializer
from django.views.decorators.csrf import csrf_exempt
from rest_framework.parsers import MultiPartParser
from rest_framework.decorators import api_view, parser_classes
import json
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import logging
from django.http import Http404
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils.decorators import method_decorator


#For checking file integrity
def file_hash(file):
    hash_sha256 = hashlib.sha256()
    for chunk in file.chunks():
        hash_sha256.update(chunk)
    return hash_sha256.hexdigest()


@login_required
@api_view(['POST'])
@parser_classes([MultiPartParser])
def upload_document(request, product_id, folder_id):
    product = get_object_or_404(Product, id=product_id)
    folder = get_object_or_404(Folder, id=folder_id, product_id=product_id)

    if product.user != request.user:
        messages.error(request, "You are not authorized to perform this action.")
        return redirect(reverse('products:product_explorer_folder', kwargs={'product_id': product_id, 'folder_id': folder_id}))

    if request.method == 'POST':
        try:
            document_files = request.FILES.getlist('document_files')
            document_types = json.loads(request.POST.get('document_types'))
            comments = json.loads(request.POST.get('comments'))

            for file, doc_type, comment in zip(document_files, document_types, comments):
                data = {
                    'folder': folder.id,
                    'original_filename': file.name,
                    'document_type': doc_type,
                    'file': file,
                    'uploaded_by': request.user.id,
                    'comments': comment
                }
                serializer = DocumentSerializer(data=data)
                if serializer.is_valid():
                    serializer.save()
                else:
                    return JsonResponse({'success': False, 'errors': serializer.errors}, status=400)

            return JsonResponse({'success': True, 'message': 'Documents uploaded'}, status=201)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class UploadDocumentPartnerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, folder_id):
        print("UploadDocumentPartnerView")
        folder = get_object_or_404(Folder, id=folder_id)
        company_profile = CompanyProfile.objects.filter(partners_contract_folder=folder).first()
        partnership = Partnership.objects.filter(
            (Q(partner1=company_profile.user_profile.user) | Q(partner2=company_profile.user_profile.user)) &
            (Q(partner1=request.user) | Q(partner2=request.user))
        ).first()

        if not partnership:
            return Response({'error': 'No partnership associated with this company profile.'}, status=403)

        if not company_profile:
            return Response({'error': 'No company profile associated with this folder.'}, status=404)

        files = request.FILES.getlist('document_files')
        comments_list = request.POST.getlist('comments[]')

        try:
            with transaction.atomic():
                documents = []
                for file, comment in zip(files, comments_list):
                    hasher = hashlib.sha256()
                    for chunk in file.chunks():
                        hasher.update(chunk)
                    file_hash = hasher.hexdigest()

                    document = Document.objects.create(
                        folder=folder,
                        original_filename=file.name,
                        file=file,
                        file_hash=file_hash,
                        uploaded_by=request.user,
                        comments=comment,
                    )
                    documents.append(document)

                # Serialize the documents for the response
                serializer = DocumentSerializer(documents, many=True)
                return Response({'message': 'Documents uploaded successfully.', 'documents': serializer.data}, status=201)
        except Exception as e:
            return Response({'error': f'Failed to upload documents. Error: {str(e)}'}, status=400)


@login_required
@require_POST
@transaction.atomic
def upload_document_to_partner_export(request, partner_export_id):
    partner_export = get_object_or_404(PartnerExport, id=partner_export_id)
    document_files = request.FILES.getlist('document_file')
    comments_list = request.POST.getlist('comments[]')

    if not partner_export.folder:
        return JsonResponse({'success': False, 'error': 'Folder not found or not created.'}, status=400)
    
    if not document_files:
        return JsonResponse({'success': False, 'error': 'No document files provided.'}, status=400)

    documents = []
    for file, comment in zip(document_files, comments_list):
        hash_digest = file_hash(file)  # Make sure file_hash function is defined
        document = Document.objects.create(
            file=file,
            uploaded_by=request.user,
            comments=comment,
            file_hash=hash_digest,
            folder=partner_export.folder
        )
        ExportDocument.objects.create(
            partner_export=partner_export,
            document=document,
            folder=partner_export.folder
        )
        documents.append(document.original_filename)

    return JsonResponse({
        'success': True,
        'message': 'Documents uploaded successfully.',
        'documents': documents
    })


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
def edit_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)

    if request.method == 'POST':
        serializer = DocumentSerializer(data=request.data, instance=document)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse({'success': True, 'message': 'Document updated'})
        else:
            print(serializer.errors)
            return JsonResponse({'success': False, 'errors': serializer.errors}, status=400)

    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)


@login_required
def ajax_get_document_details(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    document_types = DocumentType.objects.all().values('id', 'type_name')

    # Check if the document has any versions
    if document.versions.exists():
        # If it does, get the latest version
        latest_version = document.versions.latest('created_at')
        data = {
            'document_type_id': latest_version.document.document_type_id,
            'document_types': list(document_types),
            'original_filename': latest_version.original_filename,
            'comments': latest_version.comments,
        }
    else:
        # If it doesn't, use the original document data
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
def ajax_document_versions(request, document_id):
    original_document = get_object_or_404(Document, id=document_id)
    user = request.user

    # Determine if the user is the owner
    is_owner = original_document.uploaded_by == user

    # Fetch all versions
    versions = DocumentVersion.objects.filter(document=original_document).order_by('-version')

    # Filter versions based on access rights
    if not is_owner:
        # Non-owners see only their updates and the owner's updates
        versions = versions.filter(uploaded_by__in=[user, original_document.uploaded_by])

    versions_data = [{
        'version': version.version,
        'filename': version.original_filename,
        'modified': localtime(version.created_at).strftime("%Y-%m-%d %H:%M"),
        'uploader': version.uploaded_by.username,
        'download_url': reverse('documents:download_document', kwargs={'document_id': original_document.id, 'version_id': version.id})
    } for version in versions]

    # Include the original document as Version 1, if not present
    if not versions or (versions and versions.last().version != 1):
        versions_data.append({
            'version': 1,
            'filename': original_document.original_filename,
            'modified': localtime(original_document.created_at).strftime("%Y-%m-%d %H:%M"),
            'uploader': original_document.uploaded_by.username,
            'download_url': reverse('documents:download_document', kwargs={'document_id': original_document.id})
        })

    data = {
        'is_owner': is_owner,
        'original_filename': original_document.original_filename,
        'versions': versions_data
    }
    return JsonResponse(data)


class UpdateDocument(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, document_id):
        document = get_object_or_404(Document, id=document_id)
        user = request.user

        # Check if the user is the owner or has access
        is_owner = document.uploaded_by == user
        has_access = AccessPermission.objects.filter(partner2=user, document=document).exists()

        if not (is_owner or has_access):
            return Response({"detail": "You do not have permission to update this document."}, status=status.HTTP_403_FORBIDDEN)

        serializer = DocumentUpdateSerializer(document, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Document updated successfully'}, status=200)
        else:
            return Response(serializer.errors, status=400)


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


@require_POST  # Ensures only POST requests are handled
@login_required
def delete_document(request, document_id):

    if not request.user.is_authenticated:
        # Redirect or show an error if the user is not authenticated
        return redirect('account_login')  # Replace 'account_login' with your login view's name

    document = get_object_or_404(Document, id=document_id)

    if not document.uploaded_by == request.user:
        return HttpResponse("You do not have permission to delete this document.", status=403)

    if document.folder and document.folder.product:
        product_id = document.folder.product.id
        redirect_url = 'products:product_explorer_bin'
    else:
        # If no product is associated, use a default redirect
        product_id = None
        company_profile = CompanyProfile.objects.filter(partners_contract_folder=document.folder).first()
        partnership = Partnership.objects.filter(
            (Q(partner1=company_profile.user_profile.user) | Q(partner2=company_profile.user_profile.user)) &
            (Q(partner1=request.user) | Q(partner2=request.user))
        ).first()
        partner_id = partnership.pk
        redirect_url = 'partners:partner_company_profile'

    # Delete all versions of the document
    document.versions.all().delete()  # This deletes all related DocumentVersion instances

    # Delete the document itself
    document.delete()

    # Redirect back to the appropriate folder view
    if product_id:
        return redirect(redirect_url, product_id=product_id)
    else:
        return redirect(redirect_url, partner_id=partner_id)


@login_required
def move_to_bin_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    parent_id = document.folder.id
    bin_folder = Folder.objects.get_or_create(name="Bin", product=document.folder.product, is_bin=True)[0]
    handle_item_action("move_to_bin", document, bin_folder=bin_folder)
    clean_bins()
    return redirect('products:product_explorer_folder', product_id=document.folder.product.id, folder_id=parent_id)


@login_required
def restore_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    handle_item_action("restore", document)
    return redirect('products:product_explorer_bin', product_id=document.folder.product.id)



@login_required
def download_document(request, document_id, version_id=None):
    if version_id:
        version = get_object_or_404(DocumentVersion, id=version_id)
        file_path = version.file.path
        document = version.document
        download_filename = f"{version.original_filename.split('.')[0]}.{version.original_filename.split('.')[-1]}"
    else:
        document = get_object_or_404(Document, pk=document_id)
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
def comment_versions(request, document_id):
    original_document = get_object_or_404(Document, id=document_id)
    versions = DocumentVersion.objects.filter(document=original_document).order_by('-version')
    return render(request, 'documents/comment_versions.html', {
        'original_document': original_document,
        'versions': versions
    })


@login_required
def ajax_comments_versions(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    user = request.user

    # Check if the user is the owner
    is_owner = document.uploaded_by == user

    # Fetch all versions
    versions = DocumentVersion.objects.filter(document=document).order_by('-version')

    # Filter versions based on access rights
    if not is_owner:
        # Non-owners see only their updates and the owner's updates
        versions = versions.filter(uploaded_by__in=[user, document.uploaded_by])
    
    versions_data = [{
        'id': version.id,
        'version': version.version,
        'comment': version.comments or "No comment",
        'is_editable': version.uploaded_by == user or is_owner,
        'modified': localtime(version.updated_at).strftime("%Y-%m-%d %H:%M"),  # Formatting date
        'uploader': version.uploaded_by.username,
    } for version in versions]


    # Check if the initial comment is present in versions, if not, manually add the original document's comment
    if not versions or (versions and versions.last().version != 1):
        versions_data.append({
            'id': document.id,
            'version': 1,
            'comment': document.comments or "No initial comment",
            'is_editable': is_owner,
            'modified': localtime(document.updated_at).strftime("%Y-%m-%d %H:%M"),  # Formatting date
            'uploader': document.uploaded_by.username,
        })

    return JsonResponse({
        'is_owner': is_owner,
        'versions': versions_data
    })



logger = logging.getLogger(__name__)

class EditComment(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, document_id, version_number=None):
        logger.debug(f"Received request for document_id: {document_id} with version_number: {version_number}")
        if version_number is not None:
            if version_number == 1:
                # Try to fetch the document as version 1
                instance = get_object_or_404(Document, id=document_id)
                serializer_class = DocumentCommentSerializer
            else:
                # Fetch other versions normally
                instance = get_object_or_404(DocumentVersion, document_id=document_id, version=version_number)
                serializer_class = DocumentVersionCommentSerializer
            logger.debug(f"Editing version instance: {instance}")
        else:
            instance = get_object_or_404(Document, id=document_id)
            logger.debug(f"Editing document instance: {instance}")
            serializer_class = DocumentCommentSerializer

        serializer = serializer_class(instance, data=request.data)
        if serializer.is_valid():
            serializer.save()
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