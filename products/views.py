# products/views.py

from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Product
from .forms import ProductForm
from folder.models import Folder  # Assuming the Folder model is in the folder app
from django.http import JsonResponse
from django.db.models import Q
from django.urls import reverse
from document_types.models import DocumentType
from django.core.paginator import Paginator
from documents.models import Document
from django.template.loader import render_to_string
from django.db import transaction
from partners.utils import get_partner_info
from folder.utils import clean_bins
from access_control.utils import user_has_access_to
from folder.serializers import FolderSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import TemplateHTMLRenderer, JSONRenderer
from folder.serializers import FolderSerializer
from document_types.serializers import DocumentTypeSerializer
from rest_framework import generics
from .serializers import ProductSerializer, MoveEntitiesSerializer
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from access_control.models import AccessPermission
from django.core.signing import Signer, BadSignature
from access_control.utils import AccessControlMixin
from companies.models import CompanyProfile
from rest_framework.exceptions import ValidationError
from users.utils import log_user_activity
from access_control.utils import company_has_access_to
from django.http import HttpResponseForbidden
from .utils import redirect_to_correct_view

import logging

signer = Signer()

logger = logging.getLogger(__name__)


class ProductListView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'products/product_list.html'
    
    def get(self, request, *args, **kwargs):
        user_company_profile = request.user.userprofile.company_profiles.first()
        if not user_company_profile:
            logger.error(f"No company profile found for the user {request.user}.")
            return redirect('companies:company_profile_view')  # Redirect to company profile view

        current_sort = request.query_params.get('sort', 'updated_at')
        current_direction = request.query_params.get('direction', 'desc')
        filter_type = request.query_params.get('filter_type', 'product_code')
        filter_value = request.query_params.get('filter_value', '')

        combined_filter = Q(company=user_company_profile) | Q(accesspermission__partner2=user_company_profile)
        if filter_value:
            combined_filter &= Q(**{f'{filter_type}__icontains': filter_value})

        order = f'{"" if current_direction == "asc" else "-"}{current_sort}'
        products = Product.objects.filter(combined_filter).order_by(order).distinct()

        product_count = products.count()

        products_with_details = []
        for product in products:
            company_profile = product.company
            products_with_details.append({
                'product': product,
                'company_name': company_profile.name if company_profile else 'No Company',
                'signed_product_uuid': signer.sign(str(product.uuid)),
                'signed_root_folder_uuid': signer.sign(str(Folder.objects.filter(product=product, name='Root').first().uuid)) if Folder.objects.filter(product=product, name='Root').exists() else None,
                'is_owner': product.company == user_company_profile
            })

        paginator = Paginator(products_with_details, 18)
        page_obj = paginator.get_page(request.query_params.get('page', 1))

        form = ProductForm()
        
        context = {
            'page_obj': page_obj,
            'current_sort': current_sort,
            'current_direction': current_direction,
            'filter_value': filter_value,
            'filter_type': filter_type,
            'product_count': product_count if product_count > 0 else 0,
            'form': form,
        }
        return Response(context)



class ListProductsAPIView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return Product.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({'products': serializer.data})  # Ensure this structure



class CreateProductView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.user = request.user
            try:
                user_profile = request.user.userprofile
                company_profile = user_profile.company_profiles.first()
                if not company_profile:
                    raise ValidationError('No company profile associated with the user.')
                product.company = company_profile
            except:
                return Response({'error': 'Error occurred. Please try again later.'}, status=status.HTTP_400_BAD_REQUEST)
            product.save()
            uuid = signer.sign(str(product.uuid))
            return Response({'message': 'Product created', 'uuid': uuid}, status=status.HTTP_201_CREATED)
        else:
            # Converting errors to a more usable JSON format
            errors = {field: [str(e) for e in errors] for field, errors in form.errors.items()}
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)



class EditProductView(AccessControlMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_object_to_check(self, request, *args, **kwargs):
        try:
            unsigned_product_uuid = signer.unsign(kwargs.get('product_uuid'))
            product = get_object_or_404(Product, uuid=unsigned_product_uuid)
            return product
        except BadSignature:
            return None
    
    def has_access(self, user_company_profile, obj):
        # Check if the company profile of the user is the same as the company profile of the product
        return obj.company == user_company_profile
        
    def get(self, request, product_uuid, format=None):
        product = self.get_object_to_check(request, product_uuid=product_uuid)
        if not product:
            return Response({'error': 'Product not found or invalid UUID'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProductSerializer(product)
        product_types = Product.PRODUCT_TYPES
        return Response({'product': serializer.data, 'product_types': product_types})

    def put(self, request, product_uuid, format=None):
        product = self.get_object_to_check(request, product_uuid=product_uuid)
        if not product:
            return Response({'error': 'Product not found or invalid UUID'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProductSerializer(product, data=request.data, partial=True)
        if serializer.is_valid():
            try:

                # Keep track of the changes
                updated_fields = []
                for field in serializer.validated_data:
                    old_value = getattr(product, field)
                    new_value = serializer.validated_data[field]
                    if old_value != new_value:
                        updated_fields.append(f"{field} from '{old_value}' to '{new_value}'")
                
                serializer.save()

                # Create an action message detailing the changes
                if updated_fields:
                    action_message = f"Updated product '{product.product_name}': " + ", ".join(updated_fields)
                else:
                    action_message = f"Updated product '{product.product_name}' with no changes."

                # Log the product update action
                log_user_activity(
                    user=request.user,
                    action=action_message,
                    activity_type="PRODUCT_UPDATE"
                )

                return Response({"message": "Product updated"}, status=status.HTTP_200_OK)
            except IntegrityError as e:
                error_msg = str(e)
                if "product_user_id_product_code_53834cce_uniq" in error_msg:
                    return Response({'errors': {'product_code': ['This product code is already in use.']}}, status=status.HTTP_400_BAD_REQUEST)
                return Response({'errors': {'non_field_errors': [error_msg]}}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)



class ProductExplorerView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [TemplateHTMLRenderer, JSONRenderer]
    template_name = 'products/product_explorer.html'

    def get(self, request, product_uuid, folder_uuid=None, item_id=None, item_type=None):
        logger.debug("Fetching product explorer view...")

        try:
            unsigned_product_uuid = signer.unsign(product_uuid)
            logger.debug(f"Unsigned product UUID: {unsigned_product_uuid}")

            product = get_object_or_404(Product, uuid=unsigned_product_uuid)

            response = redirect_to_correct_view(request, product, 'ProductExplorerView')
            if response:  # Redirect only if needed
                return response
            
            root_folder, _ = Folder.objects.get_or_create(product=product, name='Root', defaults={'parent': None})
            logger.debug(f"Root folder: {root_folder}")

            if folder_uuid:
                unsigned_folder_uuid = signer.unsign(folder_uuid)
                current_folder = get_object_or_404(Folder, uuid=unsigned_folder_uuid)
                logger.debug(f"Current folder UUID: {unsigned_folder_uuid}, Folder: {current_folder}")

            else:
                current_folder = root_folder
                logger.debug("No folder UUID provided, using root folder.")

            exclude_partner_uuids = []
            if item_type and item_id:
                logger.debug(f"Handling item access exclusion for item_type: {item_type}, item_id: {item_id}")

                item_model = Document if item_type == "document" else Folder
                item = get_object_or_404(item_model, pk=item_id)

                # Get the user's company profile
                company_profile = request.user.userprofile.company_profiles.first()

                # Find all AccessPermissions related to the item
                permissions = AccessPermission.objects.filter(Q(document=item) | Q(folder=item)).select_related('partner1', 'partner2')

                # Determine the real partner based on the relationship
                for permission in permissions:
                    real_partner = permission.partner2 if permission.partner1 == company_profile else permission.partner1
                    exclude_partner_uuids.append(real_partner.uuid)
                    logger.debug(f"Excluding partner: {real_partner}")

            exclude_partner_uuids = list(set(exclude_partner_uuids))  # Remove duplicates
            logger.debug(f"Final exclude_partner_uuids: {exclude_partner_uuids}")

            # Fetch the user's company profile
            company_profile = request.user.userprofile.company_profiles.first()
            partner_info = get_partner_info(company_profile, exclude_partner_uuids)
            logger.debug(f"Partner info: {partner_info}")

            # Initialize subfolders and documents to empty values to avoid the UnboundLocalError
            subfolders = Folder.objects.none()
            documents = Document.objects.none()

            # Check access to current folder
            if user_has_access_to(company_profile, current_folder):
                logger.debug(f"User has access to the current folder: {current_folder}")
                subfolders = Folder.objects.filter(parent=current_folder).order_by('name')
                documents = Document.objects.filter(folder=current_folder).order_by('original_filename')
            else:
                logger.warning(f"User does not have access to the current folder: {current_folder}")

            logger.debug(f"Subfolders: {subfolders.count()}, Documents: {documents.count()}")

            document_types = DocumentType.objects.all()

            accessible_folders = [folder for folder in subfolders if user_has_access_to(company_profile, folder)]
            accessible_documents = [document for document in documents if user_has_access_to(company_profile, document)]
            logger.debug(f"Accessible folders: {len(accessible_folders)}, Accessible documents: {len(accessible_documents)}")


            breadcrumbs = [{'id': signer.sign(str(root_folder.uuid)), 'name': product.product_name}]
            if current_folder != root_folder:
                folder_ancestors = list(current_folder.get_ancestors(include_self=True))
                breadcrumbs.extend([{'id': signer.sign(str(folder.uuid)), 'name': folder.name} for folder in folder_ancestors[1:]])

            logger.debug(f"Breadcrumbs: {breadcrumbs}")

            signed_subfolders = [{'uuid': signer.sign(str(folder.uuid)), 'name': folder.name, 'parent': signer.sign(str(folder.parent.uuid)) if folder.parent else '', 'updated_at': folder.updated_at} for folder in accessible_folders]
            signed_documents = [{'uuid': signer.sign(str(document.uuid)), 'name': document.original_filename, 'folder': signer.sign(str(document.folder.uuid)), 'updated_at': document.updated_at, 'version': document.version} for document in accessible_documents]

            accessible_folders = [folder for folder in subfolders if user_has_access_to(company_profile, folder)]
            accessible_documents = [document for document in documents if user_has_access_to(company_profile, document)]

            total_folder_count = Folder.objects.filter(product=product).count() - 2
            total_document_count = Document.objects.filter(folder__product=product).count()
            
            accessible_folder_count = sum(1 for folder in Folder.objects.filter(product=product) if user_has_access_to(company_profile, folder)) - 1
            accessible_document_count = sum(1 for document in Document.objects.filter(folder__product=product) if user_has_access_to(company_profile, document))

            logger.debug(f"Total folders: {total_folder_count}, Total documents: {total_document_count}")
            logger.debug(f"Accessible folders: {accessible_folder_count}, Accessible documents: {accessible_document_count}")

            if request.user == product.user:
                folder_count = total_folder_count
                document_count = total_document_count
            else:
                folder_count = accessible_folder_count
                document_count = accessible_document_count



            context = {
                'partners': partner_info,
                'product': product,
                'current_folder': FolderSerializer(current_folder).data,
                'root_folder': root_folder,
                'subfolders': signed_subfolders,
                'documents': signed_documents,
                'document_types': DocumentTypeSerializer(document_types, many=True).data,
                'breadcrumbs': breadcrumbs,
                'is_owner': product.user == request.user,
                'total_folder_count': folder_count,
                'total_document_count': document_count,
                'signed_product_uuid': signer.sign(str(product.uuid)),
                'signed_current_folder_uuid': signer.sign(str(current_folder.uuid)),
            }

            if request.accepted_renderer.format == 'html':
                return Response(context)
            else:
                return Response(context)

        except (Product.DoesNotExist, BadSignature):
            return Response({'error': 'Product not found or invalid UUID'}, status=status.HTTP_404_NOT_FOUND)
            


class PartnerProductExplorerView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [TemplateHTMLRenderer, JSONRenderer]
    template_name = 'products/partner_product_explorer.html'

    def get(self, request, product_uuid, partner_uuid, folder_uuid=None):
        logger.debug("Fetching partner product explorer view...")

        try:
            unsigned_product_uuid = signer.unsign(product_uuid)
            unsigned_partner_uuid = signer.unsign(partner_uuid)
            logger.debug(f"Unsigned product UUID: {unsigned_product_uuid}")
            logger.debug(f"Unsigned partner UUID: {unsigned_partner_uuid}")
            

            product = get_object_or_404(Product, uuid=unsigned_product_uuid)
            partner = get_object_or_404(CompanyProfile, uuid=unsigned_partner_uuid)


            response = redirect_to_correct_view(request, product, 'PartnerProductExplorerView')
            if response:  # Redirect only if needed
                return response
            
            partner_permissions = AccessPermission.objects.filter(
                (Q(partner1=request.user.userprofile.company_profiles.first()) | 
                 Q(partner2=request.user.userprofile.company_profiles.first())) & 
                Q(product=product)
            )

            if not partner_permissions.exists():
                return HttpResponseForbidden("You do not have permission to access this content.")
            
            user_company_profile = request.user.userprofile.company_profiles.first()

            # Check if the user is the owner or the partner
            if user_company_profile != product.company and user_company_profile != partner:
                return Response({'error': 'You do not have access to this page'}, status=status.HTTP_403_FORBIDDEN)

            # Get the root folder
            root_folder, _ = Folder.objects.get_or_create(product=product, name='Root', defaults={'parent': None})

            if folder_uuid:
                unsigned_folder_uuid = signer.unsign(folder_uuid)
                current_folder = get_object_or_404(Folder, uuid=unsigned_folder_uuid)
            else:
                current_folder = root_folder

            # Get the folders and documents that have been shared with the partner
            subfolders = Folder.objects.filter(parent=current_folder).order_by('name')
            documents = Document.objects.filter(folder=current_folder).order_by('original_filename')

            # Filter based on access permissions for the specific partner
            accessible_folders = []
            for folder in subfolders:
                if AccessPermission.objects.filter(partner2=partner, folder=folder).exists():
                    accessible_folders.append(folder)

            accessible_documents = []
            for document in documents:
                if AccessPermission.objects.filter(partner2=partner, document=document).exists():
                    accessible_documents.append(document)

            # Build breadcrumbs
            breadcrumbs = [{'id': signer.sign(str(root_folder.uuid)), 'name': product.product_name}]
            if current_folder != root_folder:
                folder_ancestors = list(current_folder.get_ancestors(include_self=True))
                breadcrumbs.extend([{'id': signer.sign(str(folder.uuid)), 'name': folder.name} for folder in folder_ancestors[1:]])

            document_types = DocumentType.objects.all()

            context = {
                'product': product,
                'partner': partner,
                'current_folder': FolderSerializer(current_folder).data,
                'root_folder': root_folder,
                'subfolders': [{'uuid': signer.sign(str(folder.uuid)), 'name': folder.name, 'parent': signer.sign(str(folder.parent.uuid)) if folder.parent else '', 'updated_at': folder.updated_at} for folder in accessible_folders],
                'documents': [{'uuid': signer.sign(str(document.uuid)), 'name': document.original_filename, 'folder': signer.sign(str(document.folder.uuid)), 'updated_at': document.updated_at, 'version': document.version} for document in accessible_documents],
                'document_types': DocumentTypeSerializer(document_types, many=True).data,
                'breadcrumbs': breadcrumbs,
                'is_owner': product.company == user_company_profile,
                'signed_product_uuid': product_uuid,
                'signed_partner_uuid': partner_uuid,
                'signed_current_folder_uuid': signer.sign(str(current_folder.uuid)),
            }

            return Response(context)

        except (Product.DoesNotExist, BadSignature):
            return Response({'error': 'Product or Partner not found or invalid UUID'}, status=status.HTTP_404_NOT_FOUND)


@login_required
def product_explorer_bin(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    is_owner = (product.user == request.user)

    root_folder, _ = Folder.objects.get_or_create(product=product, name='Root', defaults={'parent': None})
    bin_folder = Folder.objects.get_or_create(product=product, name='Bin', is_bin=True)[0]  # Get or create the bin folder

    subfolders = Folder.objects.filter(parent=bin_folder).order_by('name')
    documents = Document.objects.filter(folder=bin_folder).order_by('original_filename')
    breadcrumbs = [{'id': bin_folder.id, 'name': 'Bin'}]  # Simplified breadcrumbs just for the bin

    context = {
        "bin": True,
        'product': product,
        'current_folder': bin_folder,
        'root_folder': root_folder,
        'subfolders': subfolders,
        'documents': documents,
        'breadcrumbs': breadcrumbs,
        'active_page': 'Bin',  # Additional context to highlight the bin page in navigation if needed
        'is_owner': is_owner,
    }
    clean_bins()
    return render(request, 'products/product_explorer.html', context)


class DeleteProductView(AccessControlMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get_object_to_check(self, request, *args, **kwargs):
        try:
            unsigned_product_uuid = signer.unsign(kwargs.get('product_uuid'))
            return get_object_or_404(Product, uuid=unsigned_product_uuid)
        except BadSignature:
            return None

    # Override has_access to check based on the company, not the user directly
    def has_access(self, company_profile, product):
        # Ensure the company has access to delete the product
        return product.company == company_profile

    def delete(self, request, product_uuid, format=None):
        product = self.get_object_to_check(request, product_uuid=product_uuid)
        if not product:
            return self.handle_permission_denied(request)

        try:
            Folder.objects.filter(product=product).delete()
            product.delete()
            return Response({"message": "Product deleted"}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@login_required
def home_view(request):
    products_with_root = []  # A new list to hold products with their root folder ID

    if request.user.is_authenticated:
        products = Product.objects.filter(user=request.user)
        for product in products:
            # Attempt to get the root folder for each product
            root_folder = Folder.objects.filter(product=product, name='Root').first()
            if root_folder:
                # Append both the product and its root folder ID to the list
                products_with_root.append({
                    'product': product,
                    'root_folder_id': root_folder.uuid
                })
            else:
                # Handle case where no root folder is found
                products_with_root.append({
                    'product': product,
                    'root_folder_id': None
                })
    else:
        products_with_root = []

    return render(request, 'home.html', {'products_with_root': products_with_root})


class MoveEntitiesView(APIView):

    def get(self, request, product_uuid, entity_type, entity_uuid, current_folder_uuid=None):
        try:
            unsigned_product_uuid = signer.unsign(product_uuid)
            unsigned_entity_uuid = signer.unsign(entity_uuid)
            unsigned_current_folder_uuid = signer.unsign(current_folder_uuid) if current_folder_uuid else None
        except BadSignature:
            return JsonResponse({'error': 'Invalid UUID'}, status=400)

        product = get_object_or_404(Product, uuid=unsigned_product_uuid)
        root_folder, _ = Folder.objects.get_or_create(product=product, name='Root', defaults={'parent': None})
        current_folder = get_object_or_404(Folder, uuid=unsigned_current_folder_uuid) if unsigned_current_folder_uuid else root_folder

        entity = get_object_or_404(Folder if entity_type == 'folder' else Document, uuid=unsigned_entity_uuid)

        if entity_type == 'folder':
            subfolders = Folder.objects.filter(parent=current_folder).exclude(uuid=entity.uuid).order_by('name')
        else:
            subfolders = Folder.objects.filter(parent=current_folder).order_by('name')

        documents = Document.objects.filter(folder=current_folder)

        signed_subfolders = [
            {
                'uuid': signer.sign(str(folder.uuid)),
                'name': folder.name,
                'parent': signer.sign(str(folder.parent.uuid)) if folder.parent else None,
                'updated_at': folder.updated_at
            }
            for folder in subfolders
        ]

        signed_documents = [
            {
                'uuid': signer.sign(str(document.uuid)),
                'name': document.original_filename,
                'folder': signer.sign(str(document.folder.uuid)),
                'updated_at': document.updated_at,
                'version': document.version
            }
            for document in documents
        ]

        context = {
            'product': product,
            'entity': entity,
            'entity_type': entity_type,
            'folders': signed_subfolders,
            'documents': signed_documents,
            'current_folder': current_folder,
            'current_folder_signed_uuid': signer.sign(str(current_folder.uuid)),
            'breadcrumbs': self.get_breadcrumbs(current_folder, product, root_folder),
            'signed_product_uuid': signer.sign(str(product.uuid)),
            'signed_entity_uuid': signer.sign(str(entity.uuid))
        }

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html = render_to_string('products/move_entity_fragment.html', context, request=request)
            return JsonResponse({'html': html})
        else:
            return render(request, 'products/move_entity.html', context)

    def post(self, request, product_uuid, entity_type, entity_uuid, current_folder_uuid=None):
        logger.debug("Received POST request to move entity: product_uuid=%s, entity_type=%s, entity_uuid=%s, current_folder_uuid=%s", product_uuid, entity_type, entity_uuid, current_folder_uuid)
        
        try:
            unsigned_product_uuid = signer.unsign(product_uuid)
            unsigned_entity_uuid = signer.unsign(entity_uuid)
            unsigned_current_folder_uuid = signer.unsign(current_folder_uuid) if current_folder_uuid else None
        except BadSignature:
            logger.error("Invalid UUID detected: product_uuid=%s, entity_uuid=%s, current_folder_uuid=%s", product_uuid, entity_uuid, current_folder_uuid)
            return JsonResponse({'error': 'Invalid UUID'}, status=400)

        product = get_object_or_404(Product, uuid=unsigned_product_uuid)

        try:
            target_folder_id = signer.unsign(request.data.get('target_folder_id'))
        except BadSignature:
            logger.error("Invalid target folder ID detected: %s", request.data.get('target_folder_id'))
            return JsonResponse({'error': 'The item is already in the designated folder.'}, status=400)

        logger.debug("Unsigned IDs: product_uuid=%s, entity_uuid=%s, current_folder_uuid=%s, target_folder_id=%s", unsigned_product_uuid, unsigned_entity_uuid, unsigned_current_folder_uuid, target_folder_id)

        if unsigned_current_folder_uuid and target_folder_id == unsigned_current_folder_uuid:
            logger.warning("Attempted to move entity to the same folder: entity_uuid=%s, folder_uuid=%s", unsigned_entity_uuid, unsigned_current_folder_uuid)
            return JsonResponse({'error': 'Cannot move entity to the same folder'}, status=400)

        data = {
            'entity_ids': [unsigned_entity_uuid],
            'entity_types': [entity_type],
            'target_folder_id': target_folder_id
        }

        serializer = MoveEntitiesSerializer(data=data)
        if serializer.is_valid():
            target_folder = serializer.validated_data['target_folder']
            try:
                with transaction.atomic():
                    for entity_id, entity_type in zip(serializer.validated_data['entity_ids'], serializer.validated_data['entity_types']):
                        entity = get_object_or_404(Folder if entity_type == 'folder' else Document, uuid=entity_id)
                        if entity_type == 'folder':
                            entity.parent = target_folder
                        else:
                            entity.folder = target_folder
                        entity.save()
                logger.info("Successfully moved entities: %s", data)
                return Response({'success': True, 'message': 'Entities moved'}, status=200)
            except Exception as e:
                logger.error("Failed to move entities for product %s: %s", unsigned_product_uuid, str(e))
                return Response({'success': False, 'message': 'Failed to move entities due to a server error.'}, status=500)
        else:
            logger.error("Validation errors: %s", serializer.errors)
            return Response({'success': False, 'errors': serializer.errors}, status=400)

    def get_breadcrumbs(self, folder, product, root_folder):
        breadcrumbs = [{'id': signer.sign(str(root_folder.uuid)), 'name': product.product_name}]
        ancestors = list(folder.get_ancestors(include_self=True))
        if ancestors and ancestors[0] == root_folder:
            breadcrumbs.extend([{'id': signer.sign(str(ancestor.uuid)), 'name': ancestor.name} for ancestor in ancestors[1:]])
        else:
            breadcrumbs.extend([{'id': signer.sign(str(ancestor.uuid)), 'name': ancestor.name} for ancestor in ancestors])
        return breadcrumbs


class FolderContentView(APIView):

    def get(self, request, product_uuid, folder_uuid):
        try:
            unsigned_product_uuid = signer.unsign(product_uuid)
            unsigned_folder_uuid = signer.unsign(folder_uuid)
        except BadSignature:
            return JsonResponse({'error': 'Invalid UUID'}, status=400)

        product = get_object_or_404(Product, uuid=unsigned_product_uuid)
        folder = get_object_or_404(Folder, uuid=unsigned_folder_uuid, product=product)
        moving_folder_id = request.GET.get('moving_folder_id', None)

        subfolders_queryset = Folder.objects.filter(parent=folder).order_by('name')
        subfolders = [
            {
                'id': signer.sign(str(subfolder.uuid)),
                'name': subfolder.name,
                'created_at': subfolder.created_at,
                'updated_at': subfolder.updated_at,
                # Add other fields you need from the subfolder
            }
            for subfolder in subfolders_queryset
        ]
        
        documents = Document.objects.filter(folder=folder)
        is_empty = not subfolders and not documents.exists()
        if moving_folder_id and moving_folder_id.isdigit():
            moving_folder_id = int(moving_folder_id)
        else:
            moving_folder_id = None

        # Determine the root folder and compute breadcrumbs
        root_folder = Folder.objects.filter(product=product, name='Root').first()
        breadcrumbs = [{'id': signer.sign(str(root_folder.uuid)), 'name': product.product_name}]

        folder_ancestors = list(folder.get_ancestors(include_self=True))
        if folder_ancestors and folder_ancestors[0] == root_folder:
            breadcrumbs.extend([{'id': signer.sign(str(ancestor.uuid)), 'name': ancestor.name} for ancestor in folder_ancestors[1:]])
        else:
            breadcrumbs.extend([{'id': signer.sign(str(ancestor.uuid)), 'name': ancestor.name} for ancestor in folder_ancestors])

        

        context = {
            'folder': folder,
            'subfolders': subfolders,
            'documents': documents,
            'is_empty': is_empty,
            'breadcrumbs': breadcrumbs,
            'moving_folder_id': moving_folder_id,
            'signed_product_uuid': product_uuid,  # Reuse the initially passed signed UUID
            'signed_folder_uuid': folder_uuid    # Reuse the initially passed signed UUID
        }

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html_content = render_to_string('partials/folder_content.html', context, request=request)
            return Response({
                'html': html_content,
                'breadcrumbs': breadcrumbs
            })
        else:
            return Response(context)
