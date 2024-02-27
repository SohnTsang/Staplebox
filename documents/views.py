from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from .models import Document
from access_control.models import AccessPermission
from products.models import Product
from folder.models import Folder
from document_types.models import DocumentType
from django.views.decorators.csrf import csrf_exempt
from django.http import FileResponse
from django.http import HttpResponse, Http404
from django.contrib.auth.decorators import login_required


@csrf_exempt
def upload_document(request, product_id, folder_id):
    if request.method == 'POST':
        try:
            folder = Folder.objects.get(id=folder_id)
            documents = []

            for key, file in request.FILES.items():
                parts = key.split('_')
                if len(parts) > 1 and parts[0] == 'file':
                    try:
                        index = parts[1]
                        document_type_id = request.POST.get(f'document_type_{index}')
                        if document_type_id:
                            document_type = DocumentType.objects.get(id=document_type_id)
                            document = Document.objects.create(
                                folder=folder,
                                document_type=document_type,
                                file=file
                            )
                            documents.append({
                                'id': document.id,
                                'name': document.file_name,
                                'size': document.file_size,
                                'type': document.file_type,
                                'uploaded_at': document.formatted_upload_date,
                                'document_type': document.document_type.type_name,
                                'version': document.version,
                            })
                        else:
                            print(f"No document type for file index {index}")
                    except DocumentType.DoesNotExist:
                        print(f"DocumentType not found for id: {document_type_id}")
                    except Exception as e:
                        print(f"Error processing file {key}: {e}")
            return JsonResponse({'success': True, 'documents': documents})
        except Exception as e:
            print(f"Exception: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

def delete_document(request, document_id):
    # Assuming you have some permission checks here
    try:
        document = Document.objects.get(id=document_id)
        document.delete()
        return JsonResponse({'success': True})
    except Document.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Document not found'}, status=404)

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