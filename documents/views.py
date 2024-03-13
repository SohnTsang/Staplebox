from django.shortcuts import get_object_or_404
from .models import Document
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




@csrf_exempt
@login_required
def upload_document(request, product_id, folder_id):
    if request.method == 'POST':
        try:
            folder = Folder.objects.get(id=folder_id)
            for key, file in request.FILES.items():
                # Assuming you're handling single file upload for simplicity
                document_type_id = request.POST.get('document_type')
                document_type = DocumentType.objects.get(id=document_type_id)
                
                Document.objects.create(
                    folder=folder,
                    document_type=document_type,
                    file=file,
                    uploaded_by=request.user
                )

            # Redirect to the product_explorer view with the current folder_id
            # Adjust 'product_explorer' to 'product_explorer_folder' if you've used that as your URL name
            return redirect(reverse('products:product_explorer_folder', kwargs={'product_id': product_id, 'folder_id': folder_id}))

        except Exception as e:
            print(f"Exception: {e}")
            # Consider adding more user-friendly error handling or logging here

    # Fallback redirect if not POST or exception occurs
    return redirect(reverse('products:product_explorer_folder', kwargs={'product_id': product_id, 'folder_id': folder_id}))


@require_POST  # Ensures only POST requests are handled
def delete_document(request, document_id):
    if request.method == 'POST':
        document = get_object_or_404(Document, id=document_id)

        product_id = document.folder.product.id
        folder_id = document.folder.id
        parent_id = document.folder.parent_id if document.folder.parent else ''  # Capture parent ID before deletion

        document.delete()

        if parent_id:
                return redirect('products:product_explorer_folder', product_id=product_id, folder_id=parent_id)
        else:
            return redirect('products:product_explorer', product_id=product_id)
    else:
        return redirect('products:product_explorer')  # Or some error handling



@login_required
def download_document(request, document_id):
    # Retrieve the document instance
    document = get_object_or_404(Document, pk=document_id)

    # Ensure the user has access to the document
    if not user_has_access(request.user, document):
        # Handle unauthorized access, e.g., by returning an HttpResponseForbidden
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("You do not have permission to download this document.")

    # Assuming 'file' is the FileField in your Document model
    file_path = document.file.path  # Use .path to get the actual file path

    # Open the file for reading, 'rb' means read in binary mode
    with open(file_path, 'rb') as file:
        # Create an HTTP response with the file content
        response = HttpResponse(file.read(), content_type='application/force-download')
        # Set the 'Content-Disposition' header to prompt a download with the filename
        response['Content-Disposition'] = f'attachment; filename="{document.file.name}"'
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