from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from .models import Document
from folder.models import Folder
from document_types.models import DocumentType
from django.views.decorators.csrf import csrf_exempt
from django.http import FileResponse

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

def download_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    response = FileResponse(document.file.open(), as_attachment=True, filename=document.file.name)
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