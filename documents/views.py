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


#For checking file integrity
def file_hash(file):
    hash_sha256 = hashlib.sha256()
    for chunk in file.chunks():
        hash_sha256.update(chunk)
    return hash_sha256.hexdigest()


@login_required
def upload_document(request, product_id, folder_id):
    if request.method == 'POST':
        folder = get_object_or_404(Folder, id=folder_id, product_id=product_id)
        try:
            files = request.FILES.getlist('document_files')
            file_names = request.POST.getlist('file_names[]')  # Assuming you're sending file names separately
            document_types = request.POST.getlist('document_types[]')
            comments_list = request.POST.getlist('comments[]')

            for file, doc_type_id, comment in zip(files, document_types, comments_list):
                hash_digest = file_hash(file)
                document_type = get_object_or_404(DocumentType, id=doc_type_id)

                Document.objects.create(
                    folder=folder,
                    original_filename=file.name,
                    document_type=document_type,
                    file=file,
                    file_hash=hash_digest,
                    uploaded_by=request.user,
                    comments=comment,
                )

            messages.success(request, 'Documents uploaded')
        except Exception as e:
            messages.error(request, f'Failed to upload documents. Error: {e}')

        return redirect(reverse('products:product_explorer_folder', kwargs={'product_id': product_id, 'folder_id': folder_id}))

    return redirect(reverse('products:product_explorer', kwargs={'product_id': product_id}))




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
def edit_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    # Determine the target for editing - the document itself or the latest version
    versions = document.versions.all()
    if versions.exists():
        latest_version = versions.latest('created_at')
        target_instance = latest_version
    else:
        target_instance = document

    if request.method == 'POST':
        form = DocumentEditForm(request.POST, request.FILES, instance=target_instance)
        if form.is_valid():
            edited_instance = form.save(commit=False)
            # Handling file updates
            if 'file' in request.FILES:
                uploaded_file = request.FILES['file']
                # Update the original_filename to reflect the uploaded file's name
                edited_instance.original_filename = uploaded_file.name
            edited_instance.save()
            document.updated_at = timezone.now()  # Ensure to import timezone from django.utilsdocument.original_filename
            document.save(update_fields=['updated_at'])
            form.save_m2m()  # Required for saving ManyToMany fields if any
            
            messages.success(request, 'Document updated')
            return redirect(reverse('products:product_explorer_folder', kwargs={
                'product_id': document.folder.product_id, 
                'folder_id': document.folder_id
            }))
    else:
        form = DocumentEditForm(instance=target_instance)

    return render(request, 'documents/edit_document.html', {
        'form': form,
        'document': document
    })


@login_required
def ajax_get_document_details(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    document_types = DocumentType.objects.all().values('id', 'type_name')
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



@login_required
def update_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    user = request.user

    # Check if the user is the owner or has been granted access
    is_owner = document.uploaded_by == user
    has_access = AccessPermission.objects.filter(partner2=user, document=document).exists()

    if not (is_owner or has_access):
        return HttpResponseForbidden("You do not have permission to update this document.")

    if request.method == 'POST':
        uploaded_file = request.FILES.get('file')
        comments = request.POST.get('comments')
        product_id = document.folder.product.id
        folder_id = document.folder.id

        if uploaded_file:
            # Assuming you have a function to compute file hash
            new_hash = file_hash(uploaded_file)
            document.update_version(uploaded_file, new_hash, comments, user)

            messages.success(request, 'Document updated')
            return redirect(reverse('products:product_explorer_folder', kwargs={'product_id': product_id, 'folder_id': folder_id}))

    return render(request, 'documents/update_document_form.html', {
        'document': document,
        'product_id': document.folder.product_id,
        'folder_id': document.folder_id
    })


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
        return redirect('products:product_explorer')

    product_id = document.folder.product.id

    # Delete all versions of the document
    document.versions.all().delete()  # This deletes all related DocumentVersion instances

    # Delete the document itself
    document.delete()

    # Redirect back to the appropriate folder view
    return redirect('products:product_explorer_bin', product_id=product_id)


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
        version_suffix = f"_version_{version.version}"
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



@login_required
def edit_comment(request, document_id, version_number=None):
    document = get_object_or_404(Document, id=document_id)
    
    if version_number is not None and int(version_number) > 1:
        version = get_object_or_404(DocumentVersion, document=document, version=version_number)
    else:
        version = None
    
    if request.method == 'POST':
        comment = request.POST.get('comment', '').strip()
        if comment:
            if version:
                version.comments = comment
                version.save()
                return JsonResponse({
                    'success': True, 
                    'message': 'Comment updated',
                    'modified': version.formatted_modified_date  # Return the new modified time
                })
            else:
                document.comments = comment
                document.save()
                return JsonResponse({
                    'success': True, 
                    'message': 'Comment updated',
                    'modified': document.formatted_modified_date  # Return the new modified time for the document
                })
        else:
            return JsonResponse({'success': False, 'error': 'No comment provided'}, status=400)

    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=405)





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