# document_types/views.py

from django.http import JsonResponse
from .models import DocumentType

def document_types_list(request, product_id, folder_id):
    document_types = DocumentType.objects.all().values('id', 'type_name')
    return JsonResponse(list(document_types), safe=False)