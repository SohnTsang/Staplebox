from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from products.models import Product
from documents.models import Document
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from partners.models import Partnership
from django.db.models import Q
from django.db.models import Max
from django.shortcuts import get_list_or_404
from partners.serializers import PartnershipSerializer
from .serializers import ExportSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework import generics, status
from .models import Export
import logging
from datetime import datetime as dt
import datetime
from rest_framework.parsers import MultiPartParser, FormParser
from folder.models import Folder
import hashlib
import zipfile
import io
from django.views import View
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from .serializers import DocumentSerializer
from documents.models import format_file_size
from rest_framework.generics import RetrieveAPIView
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache



logger = logging.getLogger(__name__)

def generate_reference_number(partner_id, export_date):
    partner_id = int(partner_id)  # Ensure partner_id is an integer
    export_date_obj = dt.strptime(export_date, '%Y-%m-%d')  # Convert string to datetime object
    export_date_str = export_date_obj.strftime('%Y%m%d')  # Use the export date provided by the user
    partner_hex = f'{partner_id:05X}'  # Convert partner ID to hexadecimal and pad to 5 digits
    prefix = f'EXP{export_date_str}'
    ref_prefix = f'{prefix}{partner_hex}'

    last_number = Export.objects.filter(reference_number__startswith=ref_prefix).aggregate(Max('reference_number'))['reference_number__max']

    if last_number:
        hex_seq = last_number[len(ref_prefix):]
        last_seq_number = int(hex_seq, 16) + 1
    else:
        last_seq_number = 1

    new_ref_number = f"{ref_prefix}{last_seq_number:05X}"
    return new_ref_number


class ExportListView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [TemplateHTMLRenderer]

    template_name = 'exports/export_list.html'

    @method_decorator(never_cache)
    def get(self, request):
        user = request.user
        partnerships = Partnership.objects.filter(
            Q(partner1=user) | Q(partner2=user),
            is_active=True
        ).prefetch_related(
            'partner1__userprofile__companyprofile',
            'partner2__userprofile__companyprofile'
        )
        user_exports = Export.objects.filter(
            Q(created_by=user) | Q(partner__in=partnerships),
            completed=False  # Exclude completed exports
        ).distinct().order_by('export_date').prefetch_related(
            'documents',
            'products',
            'partner__partner1__userprofile__companyprofile',
            'partner__partner2__userprofile__companyprofile'
        )
        all_partners = self.prepare_partners(user_exports, user)
        context = {
            'all_partners': all_partners,
            'partnerships': PartnershipSerializer(partnerships, many=True).data
        }
        if request.accepted_renderer.format == 'html':
            return Response(context)
        else:
            return Response({
                'partnerships': PartnershipSerializer(partnerships, many=True).data,
                'all_partners': all_partners
            })

    def prepare_partners(self, user_exports, user):
        all_partners = []
        for export in user_exports:
            partner = export.partner.partner2 if export.partner.partner1 == user else export.partner.partner1
            partner_profile = partner.userprofile.companyprofile
            documents = [
                {
                    'document_id': doc.id,
                    'file_name': doc.original_filename,
                    'created_at': doc.created_at.strftime('%Y-%m-%d'),
                    'comment': doc.comments,
                } for doc in export.documents.all()
            ]
            partner_info = {
                'partner_name': partner_profile.name,
                'partner_company_type': partner_profile.role,
                'partner_id': partner.id,
                'export_date': export.export_date.strftime('%Y-%m-%d'),
                'document_count': len(documents),
                'partner_exports': documents,
                'export_id': export.id,
                'reference_number': export.reference_number  # Ensure reference number is included
            }
            all_partners.append(partner_info)
        return all_partners


class ExportDetailView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'exports/export_detail.html'

    @method_decorator(never_cache)
    def get(self, request, export_id):
        try:
            export = Export.objects.prefetch_related(
                'documents',
                'products',
                'partner__partner1__userprofile__companyprofile',
                'partner__partner2__userprofile__companyprofile'
            ).get(id=export_id)
        except Export.DoesNotExist:
            return Response({'error': 'Export not found'}, status=404)

        partner = export.partner.partner2 if export.partner.partner1 == request.user else export.partner.partner1
        partner_profile = partner.userprofile.companyprofile

        documents = [
            {
                'document_id': doc.id,
                'file_name': doc.original_filename,
                'created_at': doc.created_at.strftime('%Y-%m-%d'),
                'file_size': format_file_size(doc.file.size),
                'comment': doc.comments,
                'uploaded_by': doc.uploaded_by.userprofile.companyprofile.name
            } for doc in export.documents.all()
        ]

        products = [
            {
                'id': product.id,
                'product_code': product.product_code,
                'product_name': product.product_name,
                'owner': product.user.userprofile.companyprofile.name
            } for product in export.products.all()
        ]

        context = {
            'export': {
                'id': export.id,
                'reference_number': export.reference_number,
                'label': export.label,
                'export_date': export.export_date.strftime('%Y-%m-%d'),
                'created_by': export.created_by.username,
                'created_by_id': export.created_by_id,
                'partner': {
                    'partner_name': partner_profile.name,
                    'partner_company_type': partner_profile.role,
                    'partner_id': partner.id,
                },
                'documents': documents,
                'products': products,
                'folder': export.folder.name if export.folder else None,
                'completed': export.completed  # Include the completed status
            }
        }

        if request.accepted_renderer.format == 'html':
            return Response(context)
        else:
            return Response(context['export'])



class ExportDetailAPIView(RetrieveAPIView):
    queryset = Export.objects.all()
    serializer_class = ExportSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    
@login_required
def list_partners(request):
    user = request.user
    partnerships = Partnership.objects.filter(
        Q(partner1=user) | Q(partner2=user), is_active=True
    ).select_related('partner1__userprofile__companyprofile', 'partner2__userprofile__companyprofile')

    partners = []
    for partnership in partnerships:
        if partnership.partner1 == user:
            partner_info = {
                'id': partnership.id,  # Use the partnership ID
                'partner_name': partnership.partner2.userprofile.companyprofile.name  # Ensure this path is correct
            }
        else:
            partner_info = {
                'id': partnership.id,  # Use the partnership ID
                'partner_name': partnership.partner1.userprofile.companyprofile.name  # Ensure this path is correct
            }
        partners.append(partner_info)
    return JsonResponse({'partners': partners})


class CreateExportView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser,)

    def post(self, request, *args, **kwargs):
        logger.info(f"Received POST request from user {request.user}")
        logger.info(f"Request data: {request.data}")
        logger.info(f"Files received: {request.FILES}")

        # Copy request data to ensure it is mutable
        data = request.data.copy()
        data['created_by'] = request.user.pk

        # Ensure partnership ID is correctly assigned
        partnership_id = data.get('partner')
        if not partnership_id:
            logger.error("Partnership ID is required.")
            return Response({'error': 'Partnership ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            partnership = Partnership.objects.get(id=partnership_id)
            data['partner'] = partnership.id
        except Partnership.DoesNotExist:
            logger.error("Invalid partnership ID.")
            return Response({'error': 'Invalid partnership ID.'}, status=status.HTTP_400_BAD_REQUEST)

        export_dates = request.data.getlist('export_dates[]')

        if not export_dates:
            logger.error("At least one export date is required.")
            return Response({'error': 'At least one export date is required.'}, status=status.HTTP_400_BAD_REQUEST)

        documents = request.FILES.getlist('documents')
        logger.info(f"Documents to upload: {documents}")

        # Create a list to hold multiple exports
        created_exports = []
        skipped_exports = []

        for export_date in export_dates:
            # Check if an export with the same partner and export date already exists
            if Export.objects.filter(partner=partnership, export_date=export_date).exists():
                skipped_exports.append({
                    'partner': partnership.id,
                    'export_date': export_date,
                    'reason': 'Duplicate export'
                })
                continue

            data['export_date'] = export_date
            reference_number = generate_reference_number(partnership_id, export_date)
            data['reference_number'] = reference_number

            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            folder_name = f"Folder for {partnership.id} on {export_date} {timestamp} - {reference_number}"
            folder, created = Folder.objects.get_or_create(name=folder_name)
            data['folder'] = folder.id

            documents_data = [{'file': doc, 'uploaded_by': request.user.pk, 'folder': folder.id, 'original_filename': doc.name} for doc in documents]
            logger.info(f"Documents data for serializer: {documents_data}")

            # Prepare data for serializer
            export_data = {
                'reference_number': reference_number,
                'export_date': export_date,
                'created_by': request.user.pk,
                'partner': partnership.id,
                'folder': folder.id,
                'documents': documents_data
            }
            serializer = ExportSerializer(data=export_data, context={'request': request})
            if serializer.is_valid():
                logger.info("Serializer is valid")
                export = serializer.save(created_by=request.user, partner=partnership)
                created_exports.append(export)
                logger.info(f"Export created with ID {export.id}")
            else:
                logger.error(f"Errors: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        added_count = len(created_exports)
        if added_count == 0 and skipped_exports:
            message = "No exports added. All provided exports already exist."
        else:
            message = f"{added_count} export{'s' if added_count != 1 else ''} added."

        return Response({
            'message': message,
            'created_exports': [ExportSerializer(export, context={'request': request}).data for export in created_exports],
            'skipped_exports': skipped_exports
        }, status=status.HTTP_201_CREATED)





class EditExportView(generics.UpdateAPIView):
    serializer_class = ExportSerializer
    permission_classes = [IsAuthenticated]
    queryset = Export.objects.all()

    def put(self, request, *args, **kwargs):
        logger.debug(f"Received PUT request with data: {request.data}")
        kwargs['partial'] = True  # Ensure partial updates are allowed
        return super().update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            self.perform_update(serializer)
            logger.debug("Export updated successfully.")
            return Response(serializer.data)
        else:
            logger.error(f"Update failed with errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def perform_update(self, serializer):
        serializer.save()
        logger.debug("Export updated successfully.")


class CompleteExportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, export_id):
        try:
            export = Export.objects.get(id=export_id, created_by=request.user)
            export.completed = True
            export.save()
            return Response({'message': 'Export marked as completed.'}, status=status.HTTP_200_OK)
        except Export.DoesNotExist:
            return Response({'error': 'Export not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        

class CompletedExportListView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [TemplateHTMLRenderer]

    template_name = 'exports/completed_export_list.html'

    def get(self, request):
        user = request.user
        partnerships = Partnership.objects.filter(
            Q(partner1=user) | Q(partner2=user),
            is_active=True
        ).prefetch_related(
            'partner1__userprofile__companyprofile',
            'partner2__userprofile__companyprofile'
        )
        user_exports = Export.objects.filter(
            Q(created_by=user) | Q(partner__in=partnerships),
            completed=True
        ).distinct().order_by('export_date').prefetch_related(
            'documents',
            'products',
            'partner__partner1__userprofile__companyprofile',
            'partner__partner2__userprofile__companyprofile'
        )
        all_partners = self.prepare_partners(user_exports, user)
        context = {
            'all_partners': all_partners,
            'partnerships': PartnershipSerializer(partnerships, many=True).data
        }
        if request.accepted_renderer.format == 'html':
            return Response(context)
        else:
            return Response({
                'partnerships': PartnershipSerializer(partnerships, many=True).data,
                'all_partners': all_partners
            })

    def prepare_partners(self, user_exports, user):
        all_partners = []
        for export in user_exports:
            partner = export.partner.partner2 if export.partner.partner1 == user else export.partner.partner1
            partner_profile = partner.userprofile.companyprofile
            documents = [
                {
                    'document_id': doc.id,
                    'file_name': doc.original_filename,
                    'created_at': doc.created_at.strftime('%Y-%m-%d'),
                    'comment': doc.comments,
                } for doc in export.documents.all()
            ]
            partner_info = {
                'partner_name': partner_profile.name,
                'partner_company_type': partner_profile.role,
                'partner_id': partner.id,
                'export_date': export.export_date.strftime('%Y-%m-%d'),
                'document_count': len(documents),
                'partner_exports': documents,
                'export_id': export.id,
                'reference_number': export.reference_number  # Ensure reference number is included
            }
            all_partners.append(partner_info)
        return all_partners
    
    
class AddProductsToExportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, export_id):
        try:
            export = Export.objects.get(id=export_id, created_by=request.user)
            product_ids = request.data.get('product_ids', [])
            products = Product.objects.filter(id__in=product_ids, user=request.user)
            export.products.add(*products)
            return Response({'message': 'Products added to the export.'})
        except Export.DoesNotExist:
            return Response({'error': 'Export not found.'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=400)
        

class UploadDocumentView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser,)

    FILE_SIZE_LIMIT = 10 * 1024 * 1024  # 10 MB file size limit

    def post(self, request, export_id, *args, **kwargs):
        logger.info(f"Received POST request from user {request.user} for export ID {export_id}")
        logger.info(f"Files received: {request.FILES}")

        # Get the export object
        export = get_object_or_404(Export, id=export_id, created_by=request.user)

        # Get the folder associated with the export
        folder = export.folder

        # Prepare the document data for the serializer
        documents = request.FILES.getlist('documents')
        logger.info(f"Documents to upload: {documents}")

        # Check for file size limit
        for doc in documents:
            if doc.size > self.FILE_SIZE_LIMIT:
                return Response(
                    {'error': f'File {doc.name} exceeds the size limit of {self.FILE_SIZE_LIMIT / (1024 * 1024)} MB.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        documents_data = [{'file': doc, 'uploaded_by': request.user.pk, 'folder': folder.id, 'original_filename': doc.name} for doc in documents]

        for doc_data in documents_data:
            # Compute the file hash
            file = doc_data['file']
            hash_sha256 = hashlib.sha256()
            for chunk in file.chunks():
                hash_sha256.update(chunk)
            doc_data['file_hash'] = hash_sha256.hexdigest()

            doc_serializer = DocumentSerializer(data=doc_data, context={'request': request})
            if doc_serializer.is_valid():
                logger.info("Document serializer is valid")
                document = doc_serializer.save()
                export.documents.add(document)
                logger.info(f"Added document with ID {document.id} to export {export.id}")
            else:
                logger.error(f"Document serializer errors: {doc_serializer.errors}")
                return Response(doc_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response({'message': 'Documents uploaded'}, status=status.HTTP_201_CREATED)


'''
class DeleteExport(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, format=None):
        logger.info(f"Delete request received for export ID: {pk}")
        export = get_object_or_404(Export, pk=pk)
        if request.user != export.created_by:
            logger.warning(f"User {request.user} does not have permission to delete export ID: {pk}")
            return Response({'error': 'You do not have permission to delete this export'}, status=status.HTTP_403_FORBIDDEN)
        export.delete()
        logger.info(f"Export ID: {pk} deleted successfully")
        return Response({'message': 'Export deleted'}, status=status.HTTP_200_OK)
'''

class DeleteExport(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, format=None):
        data = request.data
        if 'export_ids' in data:
            # Handling multiple deletions
            export_ids = data['export_ids']
            exports = Export.objects.filter(id__in=export_ids, created_by=request.user)
        else:
            # Handling single deletion passed as JSON for consistency
            export_id = data.get('export_id')
            exports = Export.objects.filter(pk=export_id, created_by=request.user)

        if not exports.exists():
            return Response({'error': 'Exports not found or access denied.'}, status=status.HTTP_404_NOT_FOUND)

        for export in exports:
            export.delete()

        return Response({'message': 'Export(s) deleted successfully'}, status=status.HTTP_200_OK)


class DownloadDocumentView(View):
    @method_decorator(never_cache)
    def get(self, request, document_id=None):
        if document_id:
            # Download a single document
            document = get_object_or_404(Document, id=document_id)
            response = self.download_single_document(document)
        else:
            # Download multiple documents
            document_ids = request.GET.getlist('ids')
            if not document_ids:
                return HttpResponse('No document IDs provided.', status=400)
            
            documents = Document.objects.filter(id__in=document_ids)
            if not documents:
                return HttpResponse('Documents not found.', status=404)
            
            response = self.download_multiple_documents(documents)
        
        return response
    
    def download_single_document(self, document):
        # Verify file integrity
        hasher = hashlib.sha256()
        for chunk in document.file.chunks():
            hasher.update(chunk)
        file_hash = hasher.hexdigest()
        
        if file_hash != document.file_hash:
            return HttpResponse('File integrity check failed.', status=400)
        
        response = HttpResponse(document.file, content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename={document.file_name}'
        return response
    
    def download_multiple_documents(self, documents):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for document in documents:
                hasher = hashlib.sha256()
                for chunk in document.file.chunks():
                    hasher.update(chunk)
                file_hash = hasher.hexdigest()
                
                if file_hash != document.file_hash:
                    return HttpResponse(f'File integrity check failed for document {document.id}.', status=400)
                
                zip_file.writestr(document.file_name, document.file.read())
        
        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer, content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename=documents.zip'
        return response
    

class DeleteDocumentsView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, export_id, *args, **kwargs):
        logger.info(f"Received DELETE request from user {request.user} for export ID {export_id}")
        document_ids = request.data.get('document_ids', [])

        if not document_ids:
            logger.error("No document IDs provided.")
            return Response({'error': 'No document IDs provided.'}, status=status.HTTP_400_BAD_REQUEST)

        # Get the export object
        export = get_object_or_404(Export, id=export_id, created_by=request.user)
        documents = export.documents.filter(id__in=document_ids)

        if not documents.exists():
            logger.error("No documents found with the provided IDs.")
            return Response({'error': 'No documents found with the provided IDs.'}, status=status.HTTP_404_NOT_FOUND)

        documents_deleted = documents.count()
        documents.delete()

        logger.info(f"Deleted {documents_deleted} document(s) for export ID {export_id}")
        return Response({'message': f'{documents_deleted} document(s) deleted'}, status=status.HTTP_200_OK)
    

class RemoveProductsFromExportView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, export_id, *args, **kwargs):
        logger.info(f"Received DELETE request from user {request.user} for export ID {export_id}")
        product_ids = request.data.get('product_ids', [])

        if not product_ids:
            logger.error("No product IDs provided.")
            return Response({'error': 'No product IDs provided.'}, status=status.HTTP_400_BAD_REQUEST)

        # Get the export object
        export = get_object_or_404(Export, id=export_id, created_by=request.user)
        products = export.products.filter(id__in=product_ids)

        if not products.exists():
            logger.error("No products found with the provided IDs.")
            return Response({'error': 'No products found with the provided IDs.'}, status=status.HTTP_404_NOT_FOUND)

        products_to_remove = products.count()
        export.products.remove(*products)  # Use remove() for many-to-many relationships

        logger.info(f"Removed {products_to_remove} product(s) from export ID {export_id}")
        return Response({'message': f'Removed {products_to_remove} product(s) from export'}, status=status.HTTP_200_OK)
