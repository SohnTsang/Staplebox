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
from django.core.signing import Signer, BadSignature
from django.http import Http404
from companies.models import CompanyProfile
from users.utils import log_user_activity

signer = Signer()



logger = logging.getLogger(__name__)

def generate_reference_number(partner_uuid, export_date, user_company_profile):
    try:
        # Fetch the partnership instance using the UUID
        partnership = Partnership.objects.get(uuid=partner_uuid)
        # Determine the correct partner ID based on the requesting user's company profile
        if partnership.partner1 == user_company_profile:
            partner_id = partnership.partner1.uuid
        elif partnership.partner2 == user_company_profile:
            partner_id = partnership.partner2.uuid
        else:
            raise ValueError("The requesting user's company profile is not part of the partnership.")
    except Partnership.DoesNotExist:
        raise ValueError("Invalid partnership UUID provided.")

    export_date_obj = dt.strptime(export_date, '%Y-%m-%d')
    export_date_str = export_date_obj.strftime('%Y%m%d')
    partner_hex = f'{partner_id.hex[:5].upper()}'  # Convert UUID to a string and take the first 5 characters
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
        user_company_profiles = user.userprofile.company_profiles.all()

        partnerships = Partnership.objects.filter(
            Q(partner1__in=user_company_profiles) | Q(partner2__in=user_company_profiles),
            is_active=True
        ).prefetch_related(
            'partner1__user_profiles__user',
            'partner2__user_profiles__user'
        )

        user_exports = Export.objects.filter(
            Q(created_by=user) | Q(partner__in=partnerships),
            completed=False  # Exclude completed exports
        ).distinct().order_by('export_date').prefetch_related(
            'documents',
            'products',
            'partner__partner1__user_profiles__user',
            'partner__partner2__user_profiles__user'
        )

        all_partners = self.prepare_partners(user_exports, user_company_profiles)
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

    def prepare_partners(self, user_exports, user_company_profiles):
        all_partners = []
        for export in user_exports:
            partner = export.partner.partner2 if export.partner.partner1 in user_company_profiles else export.partner.partner1
            partner_profile = partner
            documents = [
                {
                    'document_id': signer.sign(str(doc.uuid)),
                    'file_name': doc.original_filename,
                    'created_at': doc.created_at.strftime('%Y-%m-%d'),
                    'comment': doc.comments,
                } for doc in export.documents.all()
            ]
            partner_info = {
                'partner_name': partner_profile.name,
                'partner_company_type': partner_profile.role,
                'partner_id': signer.sign(str(partner_profile.uuid)),  # Sign the UUID from CompanyProfile
                'export_date': export.export_date.strftime('%Y-%m-%d'),
                'document_count': len(documents),
                'partner_exports': documents,
                'export_id': signer.sign(str(export.uuid)),  # Sign the export_id
                'reference_number': export.reference_number  # Ensure reference number is included
            }
            all_partners.append(partner_info)
        return all_partners


class ExportDetailView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'exports/export_detail.html'

    @method_decorator(never_cache)
    def get(self, request, export_uuid):
        try:
            unsigned_export_uuid = signer.unsign(export_uuid)
        except BadSignature:
            return Response({"detail": "Invalid export ID."}, status=status.HTTP_400_BAD_REQUEST)

        export = get_object_or_404(
            Export.objects.prefetch_related(
                'documents',
                'products',
                'partner__partner1__user_profiles',
                'partner__partner2__user_profiles'
            ), uuid=unsigned_export_uuid
        )

        # Determine the correct partner based on the requesting user's company profile
        user_company_profile = request.user.userprofile.company_profiles.first()
        if not user_company_profile:
            return Response({"detail": "No company profile found for the requesting user."}, status=status.HTTP_400_BAD_REQUEST)

        partner = export.partner.partner2 if export.partner.partner1 == user_company_profile else export.partner.partner1
        partner_profile = partner

        documents = [
            {
                'document_id': signer.sign(str(doc.uuid)),
                'file_name': doc.original_filename,
                'created_at': doc.created_at.strftime('%Y-%m-%d'),
                'file_size': format_file_size(doc.file.size),
                'comment': doc.comments,
                'uploaded_by': doc.uploaded_by.userprofile.company_profiles.first().name
            } for doc in export.documents.all()
        ]

        products = [
            {
                'id': signer.sign(str(product.uuid)),
                'product_code': product.product_code,
                'product_name': product.product_name,
                'owner': product.user.userprofile.company_profiles.first().name
            } for product in export.products.all()
        ]

        context = {
            'export': {
                'id': signer.sign(str(export.uuid)),
                'reference_number': export.reference_number,
                'label': export.label,
                'export_date': export.export_date.strftime('%Y-%m-%d'),
                'created_by': export.created_by.username,
                'created_by_company_profile_id': signer.sign(str(export.created_by.userprofile.company_profiles.first().uuid)),
                'partner': {
                    'partner_name': partner_profile.name,
                    'partner_company_type': partner_profile.role,
                    'partner_id': signer.sign(str(partner.uuid)),
                },
                'documents': documents,
                'products': products,
                'folder': export.folder.name if export.folder else None,
                'completed': export.completed
            },
            'signed_user_company_profile_id': signer.sign(str(user_company_profile.uuid))
        }

        if request.accepted_renderer.format == 'html':
            return Response(context)
        else:
            return Response(context['export'])



class ExportDetailAPIView(RetrieveAPIView):
    queryset = Export.objects.all()
    serializer_class = ExportSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        # Get the signed export UUID from the URL
        signed_export_uuid = self.kwargs['pk']

        try:
            # Unsign the UUID
            unsigned_export_uuid = signer.unsign(signed_export_uuid)
        except BadSignature:
            raise Response({"detail": "Invalid export ID."}, status=status.HTTP_400_BAD_REQUEST)

        # Retrieve the Export object using the unsigned UUID
        export = Export.objects.get(uuid=unsigned_export_uuid)

        return export

    def get_serializer_context(self):
        """
        Extra context provided to the serializer class.
        """
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    
@login_required
def list_partners(request):
    logger.debug("Entering list_partners view.")
    
    # Ensure the request method is GET
    if request.method != 'GET':
        logger.error("Invalid request method: %s", request.method)
        return JsonResponse({'error': 'Invalid request method.'}, status=400)
    
    user = request.user
    logger.debug("User: %s", user)

    # Fetch active partnerships
    user_profiles = user.userprofile.company_profiles.all()
    query = Q(partner1__in=user_profiles) | Q(partner2__in=user_profiles)
    query &= Q(is_active=True)
    partnerships = Partnership.objects.filter(query).distinct()
    logger.debug("Partnerships fetched: %s", partnerships)

    partners = []
    for partnership in partnerships:
        try:
            if partnership.partner1 in user_profiles:
                partner_profile = partnership.partner2
            else:
                partner_profile = partnership.partner1
            
            partner_name = partner_profile.name if partner_profile else "No Company"

            partner_info = {
                'uuid': signer.sign(str(partnership.uuid)),  # Use the partnership ID
                'partner_name': partner_name
            }
            partners.append(partner_info)
            logger.debug("Partner info added: %s", partner_info)
        except AttributeError as e:
            logger.error("Error accessing partner information: %s", e)
            continue

    logger.debug("Final partner list: %s", partners)
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
        signed_partnership_id = data.get('partner')
        if not signed_partnership_id:
            logger.error("Partnership ID is required.")
            return Response({'error': 'Partnership ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            partnership_id = signer.unsign(signed_partnership_id)
            partnership = Partnership.objects.get(uuid=partnership_id)
            data['partner'] = partnership.uuid
        except (Partnership.DoesNotExist, BadSignature):
            logger.error("Invalid partnership ID.")
            return Response({'error': 'Invalid partnership ID.'}, status=status.HTTP_400_BAD_REQUEST)

        export_dates = request.data.getlist('export_dates[]')

        if not export_dates:
            logger.error("At least one export date is required.")
            return Response({'error': 'At least one export date is required.'}, status=status.HTTP_400_BAD_REQUEST)

        documents = request.FILES.getlist('documents')
        logger.info(f"Documents to upload: {documents}")

        created_exports = []
        skipped_exports = []

        user_company_profile = request.user.userprofile.company_profiles.first()

        for export_date in export_dates:
            if Export.objects.filter(partner=partnership, export_date=export_date).exists():
                skipped_exports.append({
                    'partner': signed_partnership_id,
                    'export_date': export_date,
                    'reason': 'Duplicate export'
                })
                continue

            data['export_date'] = export_date
            reference_number = generate_reference_number(partnership_id, export_date, user_company_profile)
            data['reference_number'] = reference_number

            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            folder_name = f"Folder for {signed_partnership_id} on {export_date} {timestamp} - {reference_number}"
            folder, created = Folder.objects.get_or_create(name=folder_name)
            data['folder'] = folder.uuid

            documents_data = [{'file': doc, 'uploaded_by': request.user.pk, 'folder': folder.uuid, 'original_filename': doc.name} for doc in documents]
            logger.info(f"Documents data for serializer: {documents_data}")

            export_data = {
                'reference_number': reference_number,
                'export_date': export_date,
                'created_by': request.user.pk,
                'created_by_company': user_company_profile.pk if user_company_profile else None,  # Set the created_by_company field
                'partner': signed_partnership_id,
                'folder': folder.uuid,
                'documents': documents_data
            }
            serializer = ExportSerializer(data=export_data, context={'request': request})
            if serializer.is_valid():
                logger.info("Serializer is valid")
                export = serializer.save(created_by=request.user, partner=partnership)
                created_exports.append(export)
                logger.info(f"Export created with ID {export.uuid}")

                log_user_activity(
                    user=request.user,
                    action=f"Created export '{export.reference_number}'",
                    activity_type="EXPORT_CREATION"
                )
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

    def get_object(self):
        export_uuid = self.kwargs.get('export_uuid')
        try:
            unsigned_export_uuid = signer.unsign(export_uuid)
            export = Export.objects.get(uuid=unsigned_export_uuid)
            return export
        except (Export.DoesNotExist, BadSignature):
            logger.error("Invalid export ID.")
            raise Http404

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
            response_data = serializer.data
            response_data['message'] = "Export updated successfully."
            return Response(response_data)
        else:
            logger.error(f"Update failed with errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def perform_update(self, serializer):
        instance = serializer.save()
        log_user_activity(
            user=self.request.user,
            action=f"Updated export '{instance.reference_number}'",
            activity_type="EXPORT_UPDATE"
        )
        logger.debug("Export updated successfully.")


class CompleteExportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, export_uuid):
        try:
            # Unsign the export UUID
            unsigned_export_uuid = signer.unsign(export_uuid)
            
            # Retrieve the export object
            export = Export.objects.get(uuid=unsigned_export_uuid, created_by=request.user)
            
            # Check the action from the request data
            action = request.data.get('action', 'complete').lower()
            
            if action == 'complete':
                export.completed = True
                message = 'Export marked as completed.'
            elif action == 'reopen':
                export.completed = False
                message = 'Export reopened.'
            else:
                return Response({'error': 'Invalid action.'}, status=status.HTTP_400_BAD_REQUEST)
            
            export.save()

            # Log the activity
            action_description = 'marked as completed' if export.completed else 'reopened'
            log_user_activity(
                user=request.user,
                action=f"Export '{export.reference_number}' {action_description}",
                activity_type="EXPORT_UPDATE"
            )
            
            return Response({'message': message}, status=status.HTTP_200_OK)
        
        except BadSignature:
            return Response({'error': 'Invalid export ID.'}, status=status.HTTP_400_BAD_REQUEST)
        
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
        try:
            company_profile = user.userprofile.company_profiles.first()
        except CompanyProfile.DoesNotExist:
            return Response({'error': 'Company profile not found.'}, status=status.HTTP_400_BAD_REQUEST)

        partnerships = Partnership.objects.filter(
            Q(partner1=company_profile) | Q(partner2=company_profile),
            is_active=True
        )

        user_exports = Export.objects.filter(
            Q(created_by_company=company_profile) | Q(partner__in=partnerships),
            completed=True
        ).distinct().order_by('export_date').prefetch_related(
            'documents',
            'products',
            'partner__partner1',
            'partner__partner2'
        )

        all_partners = self.prepare_partners(user_exports, company_profile)
        context = {
            'all_partners': all_partners,
            'partnerships': PartnershipSerializer(partnerships, many=True).data
        }
        if request.accepted_renderer.format == 'html':
            return Response(context, template_name=self.template_name)
        else:
            return Response({
                'partnerships': PartnershipSerializer(partnerships, many=True).data,
                'all_partners': all_partners
            })

    def prepare_partners(self, user_exports, company_profile):
        all_partners = []
        for export in user_exports:
            partner = export.partner.partner2 if export.partner.partner1 == company_profile else export.partner.partner1
            partner_profile = partner
            documents = [
                {
                    'document_id': doc.uuid,
                    'file_name': doc.original_filename,
                    'created_at': doc.created_at.strftime('%Y-%m-%d'),
                    'comment': doc.comments,
                } for doc in export.documents.all()
            ]
            partner_info = {
                'partner_name': partner_profile.name,
                'partner_company_type': partner_profile.role,
                'partner_id': partner.uuid,
                'export_date': export.export_date.strftime('%Y-%m-%d'),
                'document_count': len(documents),
                'partner_exports': documents,
                'export_id': signer.sign(str(export.uuid)),
                'reference_number': export.reference_number  # Ensure reference number is included
            }
            all_partners.append(partner_info)
        return all_partners
    
    
class AddProductsToExportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, export_uuid):
        try:
            # Unsign the export UUID
            unsigned_export_uuid = signer.unsign(export_uuid)
            
            # Retrieve the export object
            export = Export.objects.get(uuid=unsigned_export_uuid, created_by=request.user)
            
            # Get product IDs from the request data
            product_ids = request.data.get('product_ids', [])
            if not product_ids:
                return Response({'error': 'No product IDs provided.'}, status=400)
            
            # Retrieve products based on the provided IDs
            products = Product.objects.filter(uuid__in=product_ids, user=request.user)
            if not products.exists():
                return Response({'error': 'No products found for the given IDs.'}, status=404)
            
            # Add products to the export
            export.products.add(*products)

            product_names = ', '.join([product.name for product in products])

            log_user_activity(
                user=request.user,
                action=f"Added products to export '{export.reference_number}': {product_names}",
                activity_type="EXPORT_UPDATE"
            )

            return Response({'message': 'Products added to the export.'})
        
        except BadSignature:
            return Response({'error': 'Invalid export ID.'}, status=400)
        
        except Export.DoesNotExist:
            return Response({'error': 'Export not found.'}, status=404)
        
        except Exception as e:
            return Response({'error': str(e)}, status=400)
        

class UploadDocumentView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser,)

    FILE_SIZE_LIMIT = 10 * 1024 * 1024  # 10 MB file size limit

    def post(self, request, export_uuid, *args, **kwargs):
        logger.info(f"Received POST request from user {request.user} for export ID {export_uuid}")
        logger.info(f"Files received: {request.FILES}")

        try:
            # Unsign the export UUID
            unsigned_export_uuid = signer.unsign(export_uuid)

            # Get the export object
            export = get_object_or_404(Export, uuid=unsigned_export_uuid, created_by=request.user)

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

            documents_data = [{'file': doc, 'uploaded_by': request.user.pk, 'folder': folder.uuid, 'original_filename': doc.name} for doc in documents]

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
                    logger.info(f"Added document with ID {document.uuid} to export {export.uuid}")
                    # Inside the loop where documents are uploaded and saved
                    log_user_activity(
                        user=request.user,
                        action=f"Uploaded document '{document.original_filename}' to export '{export.reference_number}'",
                        activity_type="DOCUMENT_UPLOAD"
                    )
                else:
                    logger.error(f"Document serializer errors: {doc_serializer.errors}")
                    return Response(doc_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            return Response({'message': 'Documents uploaded'}, status=status.HTTP_201_CREATED)

        except BadSignature:
            logger.error("Invalid export ID signature.")
            return Response({'error': 'Invalid export ID.'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error during document upload: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class DeleteExport(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        logger.debug("DELETE request received")
        logger.debug(f"Request data: {request.data}")

        data = request.data
        export_id = data.get('export_id')
        export_ids = data.get('export_ids')

        logger.debug(f"export_id: {export_id}")
        logger.debug(f"export_ids: {export_ids}")

        if export_id:
            export_ids = [export_id]
        elif not export_ids:
            logger.warning("No export ID provided in request data.")
            return Response({'error': 'No export ID provided.'}, status=status.HTTP_400_BAD_REQUEST)

        logger.debug(f"Export IDs to delete: {export_ids}")
        deleted_exports = []

        user_company_profile = request.user.userprofile.company_profiles.first()
        if not user_company_profile:
            logger.error("User does not have a company profile.")
            return Response({'error': 'User does not have a company profile.'}, status=status.HTTP_400_BAD_REQUEST)

        for export_uuid in export_ids:
            try:
                unsigned_export_uuid = signer.unsign(export_uuid)
                logger.debug(f"Unsigned export UUID: {unsigned_export_uuid}")
                print(user_company_profile, unsigned_export_uuid)
                export = Export.objects.get(uuid=unsigned_export_uuid, created_by_company=user_company_profile)
                logger.info(f"export found {export}")
                export.delete()
                logger.info(f"Deleted export with UUID: {unsigned_export_uuid}")
                deleted_exports.append(unsigned_export_uuid)

                # After successful deletion of an export
                log_user_activity(
                    user=request.user,
                    action=f"Deleted export '{export.reference_number}'",
                    activity_type="EXPORT_UPDATE"
                )
            except BadSignature:
                logger.error(f"BadSignature: Invalid export UUID: {export_uuid}")
            except Export.DoesNotExist:
                logger.error(f"Export.DoesNotExist: No export found with UUID: {unsigned_export_uuid}")
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")

        if not deleted_exports:
            logger.error("No valid exports found or access denied.")
            return Response({'error': 'No valid exports found or access denied.'}, status=status.HTTP_404_NOT_FOUND)

        logger.debug("Exports deleted successfully")
        return Response({'message': 'Export(s) deleted successfully'}, status=status.HTTP_200_OK)



class DownloadDocumentView(View):
    @method_decorator(never_cache)
    def get(self, request, document_uuid=None):
        try:
            if document_uuid:
                # Unsign the document UUID
                unsigned_document_uuid = signer.unsign(document_uuid)
                
                # Download a single document
                document = get_object_or_404(Document, uuid=unsigned_document_uuid)
                response = self.download_single_document(document)
            else:
                # Download multiple documents
                document_uuids = request.GET.getlist('ids')
                if not document_uuids:
                    return HttpResponse('No document IDs provided.', status=400)

                # Unsign each document UUID
                unsigned_document_uuids = []
                for doc_uuid in document_uuids:
                    try:
                        unsigned_document_uuids.append(signer.unsign(doc_uuid))
                    except BadSignature:
                        return HttpResponse(f'Invalid document ID: {doc_uuid}', status=400)
                
                documents = Document.objects.filter(uuid__in=unsigned_document_uuids)
                if not documents.exists():
                    return HttpResponse('Documents not found.', status=404)
                
                response = self.download_multiple_documents(documents)
            
            return response
        except BadSignature:
            return HttpResponse('Invalid document ID.', status=400)

    def download_single_document(self, document):
        # Verify file integrity
        hasher = hashlib.sha256()
        for chunk in document.file.chunks():
            hasher.update(chunk)
        file_hash = hasher.hexdigest()
        
        if file_hash != document.file_hash:
            return HttpResponse('File integrity check failed.', status=400)
        
        response = HttpResponse(document.file, content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename={document.original_filename}'

        # Retrieve the related export(s)
        related_exports = document.exports.all()
        
        # If there are related exports, log the activity for the first one (or modify logic as needed)
        if related_exports.exists():
            export = related_exports.first()  # You can choose to log all or just the first one
            log_user_activity(
                user=self.request.user,
                action=f"Downloaded document '{document.original_filename}' from export '{export.reference_number}'",
                activity_type="DOCUMENT_DOWNLOAD"
            )
        else:
            log_user_activity(
                user=self.request.user,
                action=f"Downloaded document '{document.original_filename}'",
                activity_type="DOCUMENT_DOWNLOAD"
            )
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
                    return HttpResponse(f'File integrity check failed for document {document.uuid}.', status=400)
                
                zip_file.writestr(document.original_filename, document.file.read())
        
        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer, content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename=documents.zip'
        document_names = ', '.join([doc.original_filename for doc in documents])
        log_user_activity(
            user=self.request.user,
            action=f"Downloaded multiple documents: {document_names}",
            activity_type="DOCUMENT_DOWNLOAD"
        )
        return response
    

class DeleteDocumentsView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, export_uuid, *args, **kwargs):
        logger.info(f"Received DELETE request from user {request.user} for export ID {export_uuid}")
        document_ids = request.data.get('document_ids', [])

        if not document_ids:
            logger.error("No document IDs provided.")
            return Response({'error': 'No document IDs provided.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Unsign the export UUID
            unsigned_export_uuid = signer.unsign(export_uuid)

            # Unsign the document IDs
            unsigned_document_ids = [signer.unsign(doc_id) for doc_id in document_ids]

            # Get the export object
            export = get_object_or_404(Export, uuid=unsigned_export_uuid, created_by=request.user)
            documents = export.documents.filter(uuid__in=unsigned_document_ids)

            if not documents.exists():
                logger.error("No documents found with the provided IDs.")
                return Response({'error': 'No documents found with the provided IDs.'}, status=status.HTTP_404_NOT_FOUND)

            documents_deleted = documents.count()
            documents.delete()

            log_user_activity(
                user=request.user,
                action=f"Deleted {documents_deleted} document(s) from export '{export.reference_number}'",
                activity_type="DOCUMENT_UPDATE"
            )

            logger.info(f"Deleted {documents_deleted} document(s) for export ID {unsigned_export_uuid}")
            return Response({'message': f'{documents_deleted} document(s) deleted'}, status=status.HTTP_200_OK)

        except BadSignature:
            logger.error("Invalid export or document ID signature.")
            return Response({'error': 'Invalid export or document ID.'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error during document deletion: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    

class RemoveProductsFromExportView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, export_uuid, *args, **kwargs):
        logger.info(f"Received DELETE request from user {request.user} for export ID {export_uuid}")
        
        try:
            # Unsign the export UUID
            unsigned_export_uuid = signer.unsign(export_uuid)
            
            # Get the product IDs from the request data and unsign them
            product_ids = request.data.get('product_ids', [])
            if not product_ids:
                logger.error("No product IDs provided.")
                return Response({'error': 'No product IDs provided.'}, status=status.HTTP_400_BAD_REQUEST)
            
            unsigned_product_ids = [signer.unsign(pid) for pid in product_ids]
        
            # Get the export object
            export = get_object_or_404(Export, uuid=unsigned_export_uuid, created_by=request.user)
            products = export.products.filter(uuid__in=unsigned_product_ids)

            if not products.exists():
                logger.error("No products found with the provided IDs.")
                return Response({'error': 'No products found with the provided IDs.'}, status=status.HTTP_404_NOT_FOUND)

            products_to_remove = products.count()
            export.products.remove(*products)  # Use remove() for many-to-many relationships

            product_names = ', '.join([product.name for product in products])

            log_user_activity(
                user=request.user,
                action=f"Removed products from export '{export.reference_number}': {product_names}",
                activity_type="EXPORT_UPDATE"
            )

            logger.info(f"Removed {products_to_remove} product(s) from export ID {unsigned_export_uuid}")
            return Response({'message': f'Removed {products_to_remove} product(s) from export'}, status=status.HTTP_200_OK)
        
        except BadSignature:
            logger.error("Invalid export or product ID signature.")
            return Response({'error': 'Invalid export or product ID.'}, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error during product removal: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
