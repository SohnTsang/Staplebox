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
from django.views.decorators.http import require_http_methods
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

import logging

signer = Signer()

logger = logging.getLogger(__name__)


class ProductListView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'products/product_list.html'
    
    def get(self, request, *args, **kwargs):
        user = request.user
        current_sort = request.query_params.get('sort', 'updated_at')
        current_direction = request.query_params.get('direction', 'desc')
        filter_type = request.query_params.get('filter_type', 'product_code')
        filter_value = request.query_params.get('filter_value', '')

        combined_filter = Q(user=user) | Q(accesspermission__partner2=user)
        if filter_value:
            combined_filter &= Q(**{f'{filter_type}__icontains': filter_value})

        order = f'{"" if current_direction == "asc" else "-"}{current_sort}'
        products = Product.objects.filter(combined_filter).order_by(order).distinct()

        product_count = products.count()

        # Convert queryset to list of dicts to preserve pagination and other features
        products_with_root = [{
            'product': product,
            'signed_product_uuid': signer.sign(str(product.uuid)),  # Sign the product UUID
            'signed_root_folder_uuid': signer.sign(str(Folder.objects.filter(product=product, name='Root').first().uuid)) if Folder.objects.filter(product=product, name='Root').exists() else None
        } for product in products]

        paginator = Paginator(products_with_root, 18)  # Adjust the count as needed
        page_obj = paginator.get_page(request.query_params.get('page', 1))

        form = ProductForm()  # Initialize the create product form
        
        context = {
            'page_obj': page_obj,
            'current_sort': current_sort,
            'current_direction': current_direction,
            'filter_value': filter_value,
            'filter_type': filter_type,
            'product_count': product_count,
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
            product.save()
            uuid = signer.sign(str(product.uuid))
            return Response({'message': 'Product created', 'uuid': uuid}, status=status.HTTP_201_CREATED)
        else:
            # Converting errors to a more usable JSON format
            errors = {field: [str(e) for e in errors] for field, errors in form.errors.items()}
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)


class EditProductView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, product_uuid, format=None):
        try:
            # Unsign the product UUID
            unsigned_product_uuid = signer.unsign(product_uuid)
            product = get_object_or_404(Product, uuid=unsigned_product_uuid, user=request.user)
            serializer = ProductSerializer(product)
            product_types = Product.PRODUCT_TYPES
            return Response({'product': serializer.data, 'product_types': product_types})
        except (Product.DoesNotExist, BadSignature):
            return Response({'error': 'Product not found or invalid UUID'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, product_uuid, format=None):
        try:
            # Unsign the product UUID
            unsigned_product_uuid = signer.unsign(product_uuid)
            product = get_object_or_404(Product, uuid=unsigned_product_uuid, user=request.user)
            serializer = ProductSerializer(product, data=request.data, partial=True)
            if serializer.is_valid():
                try:
                    serializer.save()
                    return Response({"message": "Product updated"}, status=status.HTTP_200_OK)
                except IntegrityError as e:
                    error_msg = str(e)
                    if "product_user_id_product_code_53834cce_uniq" in error_msg:
                        return Response({'errors': {'product_code': ['This product code is already in use.']}}, status=status.HTTP_400_BAD_REQUEST)
                    return Response({'errors': {'non_field_errors': [error_msg]}}, status=status.HTTP_400_BAD_REQUEST)
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except (Product.DoesNotExist, BadSignature):
            return Response({'error': 'Product not found or invalid UUID'}, status=status.HTTP_404_NOT_FOUND)


class ProductExplorerView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [TemplateHTMLRenderer, JSONRenderer]
    template_name = 'products/product_explorer.html'

    def get(self, request, product_uuid, folder_uuid=None, item_id=None, item_type=None):
        try:
            unsigned_product_uuid = signer.unsign(product_uuid)
            product = get_object_or_404(Product, uuid=unsigned_product_uuid)
            root_folder, _ = Folder.objects.get_or_create(product=product, name='Root', defaults={'parent': None})

            if folder_uuid:
                unsigned_folder_uuid = signer.unsign(folder_uuid)
                current_folder = get_object_or_404(Folder, uuid=unsigned_folder_uuid)
            else:
                current_folder = root_folder


            exclude_partner_ids = []
            if item_type and item_id:
                item_model = Document if item_type == "document" else Folder
                item = get_object_or_404(item_model, pk=item_id)
                exclude_partner_ids = AccessPermission.objects.filter(
                    Q(document=item) | Q(folder=item)
                ).values_list('partner2_id', flat=True)

            partner_info = get_partner_info(request.user, exclude_partner_ids)

            breadcrumbs = [{'id': signer.sign(str(root_folder.uuid)), 'name': product.product_name}]
            if current_folder != root_folder:
                folder_ancestors = list(current_folder.get_ancestors(include_self=True))
                breadcrumbs.extend([{'id': signer.sign(str(folder.uuid)), 'name': folder.name} for folder in folder_ancestors[1:]])

            subfolders = Folder.objects.filter(parent=current_folder).order_by('name')
            documents = Document.objects.filter(folder=current_folder).order_by('original_filename')
            document_types = DocumentType.objects.all()
            
            signed_subfolders = [{'uuid': signer.sign(str(folder.uuid)), 'name': folder.name, 'parent': signer.sign(str(folder.parent.uuid)) if folder.parent else '', 'updated_at': folder.updated_at} for folder in subfolders]
            signed_documents = [{'uuid': signer.sign(str(document.uuid)), 'name': document.original_filename, 'folder': signer.sign(str(document.folder.uuid)), 'updated_at': document.updated_at, 'version': document.version} for document in documents]
            
            total_folder_count = Folder.objects.filter(product=product).count() - 2
            total_document_count = Document.objects.filter(folder__product=product).count()
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
                'total_folder_count': total_folder_count,
                'total_document_count': total_document_count,
                'signed_product_uuid': signer.sign(str(product.uuid)),
                'signed_current_folder_uuid': signer.sign(str(current_folder.uuid)),
            }

            if request.accepted_renderer.format == 'html':
                return Response(context)
            else:
                return Response(context)

        except (Product.DoesNotExist, BadSignature):
            return Response({'error': 'Product not found or invalid UUID'}, status=status.HTTP_404_NOT_FOUND)




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


class DeleteProductView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, product_uuid, format=None):
        try:
            # Unsign the product UUID
            unsigned_product_uuid = signer.unsign(product_uuid)
            product = get_object_or_404(Product, uuid=unsigned_product_uuid, user=request.user)

            # Handle related objects (like folders) here if needed
            Folder.objects.filter(product=product).delete()  # Adjust as necessary

            product.delete()
            return Response({"message": "Product deleted"}, status=status.HTTP_204_NO_CONTENT)

        except (Product.DoesNotExist, BadSignature):
            return Response({"error": "Product not found or invalid UUID"}, status=status.HTTP_404_NOT_FOUND)

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
