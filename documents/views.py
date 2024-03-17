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


#For checking file integrity
def file_hash(file):
    hash_sha256 = hashlib.sha256()
    for chunk in file.chunks():
        hash_sha256.update(chunk)
    return hash_sha256.hexdigest()

@csrf_exempt
@login_required
def upload_document(request, product_id, folder_id):
    if request.method == 'POST':
        folder = get_object_or_404(Folder, id=folder_id)
        try:
            for key, file in request.FILES.items():
                comments = request.POST.get('comments', '')
                document_type_id = request.POST.get('document_type')
                document_type = get_object_or_404(DocumentType, id=document_type_id)
                hash_digest = file_hash(file)
                
                original_filename = file.name
                # Check if the file already exists in the folder
                if Document.objects.filter(folder=folder, original_filename=original_filename).exists():
                    # Generate a new filename if it exists
                    new_filename = generate_new_filename(folder, original_filename)
                else:
                    new_filename = original_filename

                # Directly create a new document entry
                Document.objects.create(
                    folder=folder,
                    document_type=document_type,
                    file=file,
                    file_hash=hash_digest,  # Store the hash of the file
                    original_filename=new_filename,  # Use the potentially new filename
                    uploaded_by=request.user,
                    comments=comments,
                )

            # Redirect to the folder view after successful upload
            return redirect(reverse('products:product_explorer_folder', kwargs={'product_id': product_id, 'folder_id': folder_id}))
        except Exception as e:
            # Handle exceptions or logging
            print(f"Exception: {e}")

    # Redirect to the folder view if not POST or in case of exceptions
    return redirect(reverse('products:product_explorer_folder', kwargs={'product_id': product_id, 'folder_id': folder_id}))



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
            form.save_m2m()  # Required for saving ManyToMany fields if any
            
            messages.success(request, 'Update successful.')
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
def document_versions(request, document_id):
    original_document = get_object_or_404(Document, id=document_id)

    # Directly fetch versions related to the document from DocumentVersion model
    versions = DocumentVersion.objects.filter(document=original_document).order_by('-version')

    return render(request, 'documents/document_versions.html', {
        'original_document': original_document,
        'versions': versions
    })


@login_required
def update_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    if request.method == 'POST':
        uploaded_file = request.FILES.get('file')
        comments = request.POST.get('comments')  # Correctly capture the comments from the form
        product_id = request.POST.get('product_id')  # Adjusted to directly use document reference
        folder_id = request.POST.get('folder_id')  # Adjusted to directly use document reference

        if uploaded_file:
            new_hash = file_hash(uploaded_file)  # Use your file_hash function
            # Now pass the captured comments to the update_version method
            document.update_version(uploaded_file, new_hash, comments)

            messages.success(request, 'Document updated successfully!')
            return redirect(reverse('products:product_explorer_folder', kwargs={'product_id': product_id, 'folder_id': folder_id}))
    
    # If not POST or if the form is invalid, render the form again
    return render(request, 'documents/update_document_form.html', {
        'document': document,
        'product_id': document.folder.product_id,
        'folder_id': document.folder_id
    })


@require_POST  # Ensures only POST requests are handled
@login_required
def delete_document(request, document_id):
    if not request.user.is_authenticated:
        # Redirect or show an error if the user is not authenticated
        return redirect('account_login')  # Replace 'account_login' with your login view's name

    document = get_object_or_404(Document, id=document_id)

    # Check if the user has the right to delete the document
    # This is just a placeholder; you should replace it with your actual permission check
    if not document.uploaded_by == request.user:
        # Show an error or redirect if the user doesn't have permission
        # Assuming you have some way to show messages to the user
        return redirect('products:product_explorer')

    product_id = document.folder.product.id
    folder_id = document.folder.id

    # Delete all versions of the document
    document.versions.all().delete()  # This deletes all related DocumentVersion instances

    # Delete the document itself
    document.delete()

    # Redirect back to the appropriate folder view
    return redirect(reverse('products:product_explorer_folder', kwargs={'product_id': product_id, 'folder_id': folder_id}))


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
def edit_comment(request, version_id=None):
    if version_id:
        # Editing a specific version's comment
        version = get_object_or_404(DocumentVersion, id=version_id)
        document = version.document
    else:
        # Editing the original document's comment (assuming there's a way to identify it)
        document = get_object_or_404(Document, id=request.GET.get('document_id'))
        version = None

    # Perform permission check here

    if request.method == 'POST':
        comment = request.POST.get('comment', '').strip()
        if comment:
            if version:
                version.comments = comment
                version.save()
                document_id = version.document.id
            else:
                document.comments = comment
                document.save()
                document_id = document.id
            # Redirect to a success page or the document versions page
            return redirect(reverse('documents:comment_versions', kwargs={'document_id': document_id}))
    
    else:
        comment = version.comments if version else document.comments

    return render(request, 'documents/edit_comment.html', {'comment': comment, 'document': document, 'version': version})

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