from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from .models import Document
from folder.models import Folder
from document_types.models import DocumentType
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt  # For demonstration purposes; consider using CSRF protection for production
def upload_document(request, product_id, folder_id):
    if request.method == 'POST':
        # Use get_object_or_404 for better error handling
        folder = get_object_or_404(Folder, id=folder_id, product_id=product_id)
        document_type_id = request.POST.get('document_type')
        file = request.FILES.get('file')
        document_type = get_object_or_404(DocumentType, id=document_type_id)

        document = Document.objects.create(
            folder=folder,
            document_type=document_type,
            file=file,
        )

        document_name = document.file.name.split('/')[-1]

        # Return some JSON indicating success/failure
        return JsonResponse({'success': True, 'document_id': document.id, 'name': document_name, 'document_type': document.document_type.type_name})
    return JsonResponse({'success': False, 'errors': 'Invalid request'}, status=400)

def delete_document(request, document_id):
    # Assuming you have some permission checks here
    try:
        document = Document.objects.get(id=document_id)
        document.delete()
        return JsonResponse({'success': True})
    except Document.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Document not found'}, status=404)