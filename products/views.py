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
import logging

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
        products = Product.objects.filter(combined_filter).order_by(order)

        product_count = products.count()

        # Convert queryset to list of dicts to preserve pagination and other features
        products_with_root = [{
            'product': product,
            'root_folder_id': Folder.objects.filter(product=product, name='Root').first().id if Folder.objects.filter(product=product, name='Root').exists() else None
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
        print(request.POST)
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.user = request.user
            product.save()
            return Response({'message': 'Product created'}, status=status.HTTP_201_CREATED)
        else:
            # Converting errors to a more usable JSON format
            errors = {field: [str(e) for e in errors] for field, errors in form.errors.items()}
            print(errors)
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)


class EditProductView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, format=None):
        product = get_object_or_404(Product, pk=pk, user=request.user)
        serializer = ProductSerializer(product)
        product_types = Product.PRODUCT_TYPES
        return Response({'product': serializer.data, 'product_types': product_types})

    def put(self, request, pk, format=None):
        product = get_object_or_404(Product, pk=pk, user=request.user)
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




class ProductExplorerView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [TemplateHTMLRenderer, JSONRenderer]
    template_name = 'products/product_explorer.html'

    def get(self, request, product_id, folder_id=None, item_id=None, item_type=None):
        user = request.user
        partner_info = get_partner_info(user)
        product = get_object_or_404(Product, id=product_id)
        root_folder, _ = Folder.objects.get_or_create(product=product, name='Root', defaults={'parent': None})

        if folder_id and folder_id != root_folder.id:
            current_folder = get_object_or_404(Folder, id=folder_id)
        else:
            current_folder = root_folder

            # Determine item to exclude access partners
        exclude_partner_ids = []
        if item_type and item_id:
            item_model = Document if item_type == "document" else Folder
            item = get_object_or_404(item_model, pk=item_id)
            exclude_partner_ids = AccessPermission.objects.filter(
                Q(document=item) | Q(folder=item)
            ).values_list('partner2_id', flat=True)

        partner_info = get_partner_info(user, exclude_partner_ids)

        breadcrumbs = [{'id': root_folder.id, 'name': product.product_name}]
        if current_folder != root_folder:
            folder_ancestors = list(current_folder.get_ancestors(include_self=True))
            breadcrumbs.extend([{'id': folder.id, 'name': folder.name} for folder in folder_ancestors[1:]])

        subfolders = Folder.objects.filter(parent=current_folder).order_by('name')
        documents = Document.objects.filter(folder=current_folder).order_by('original_filename')
        document_types = DocumentType.objects.all()

        # Count total folders and documents
        total_folder_count = Folder.objects.filter(product=product).count() - 2

        total_document_count = Document.objects.filter(folder__product=product).count()

        context = {
            'partners': partner_info,
            'product': product,
            'current_folder': FolderSerializer(current_folder).data,
            'root_folder': root_folder,
            'subfolders': subfolders,
            'documents': documents,
            'document_types': DocumentTypeSerializer(document_types, many=True).data,
            'breadcrumbs': breadcrumbs,
            'is_owner': product.user == user,
            'total_folder_count': total_folder_count,
            'total_document_count': total_document_count,
        }

        # Determine response type based on 'Accept' header or URL parameter
        if request.accepted_renderer.format == 'html':
            return Response(context)  # Render HTML template
        else:
            return Response(context)  # Return JSON data


@login_required
def product_explorer(request, product_id, folder_id=None):
    user = request.user

    product = get_object_or_404(Product, id=product_id)
    partner_info = get_partner_info(user)

    is_owner = (product.user == user)

    root_folder, _ = Folder.objects.get_or_create(product=product, name='Root', defaults={'parent': None})

    if folder_id and folder_id != root_folder.id:
        current_folder = get_object_or_404(Folder, id=folder_id)
    else:
        current_folder = root_folder


    # Generate breadcrumbs for navigation
    breadcrumbs = [{'id': root_folder.id, 'name': product.product_name}]
    if current_folder != root_folder:
        folder_ancestors = list(current_folder.get_ancestors(include_self=True))
        breadcrumbs.extend([{'id': folder.id, 'name': folder.name} for folder in folder_ancestors[1:]])

    # Filter subfolders and documents by access permissions
    subfolders = [f for f in Folder.objects.filter(parent=current_folder).order_by('name') if user_has_access_to(request.user, f)]
    documents = [d for d in Document.objects.filter(folder=current_folder).order_by('original_filename') if user_has_access_to(request.user, d)]

    # Prepare document details for display
    document_types = DocumentType.objects.all()
    for document in documents:
        document.latest_version = document.versions.latest('created_at') if document.versions.exists() else None
        if document.latest_version:
            document.latest_uploaded_by = document.latest_version.uploaded_by
            document.latest_comment = document.latest_version.comments
            document.latest_file_size = document.latest_version.formatted_file_size
            document.latest_version_date = document.latest_version.created_at
        else:
            document.latest_uploaded_by = document.uploaded_by
            document.latest_comment = document.comments
            document.latest_file_size = document.formatted_file_size
            document.latest_version_date = document.created_at

    context = {
        'partners': partner_info,
        'product': product,
        'root_folder': root_folder,
        'current_folder': current_folder,
        'subfolders': subfolders,
        'documents': documents,
        'document_types': document_types,
        'breadcrumbs': breadcrumbs,
        'active_page': 'Products',
        'is_owner': is_owner,
    }

    return render(request, 'products/product_explorer.html', context)


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

    def delete(self, request, pk, format=None):
        try:
            product = get_object_or_404(Product, pk=pk, user=request.user)

            # Handle related objects (like folders) here if needed
            # For example, delete or reassign related folders
            Folder.objects.filter(product=product).delete()  # Adjust as necessary

            product.delete()
            return Response({"message": "Product deleted"}, status=status.HTTP_204_NO_CONTENT)

        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

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
                    'root_folder_id': root_folder.id
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
    
    def get(self, request, product_id, entity_type, entity_id, current_folder_id=None, moving_folder_id=None):
        print("Move entities view called")
        product = get_object_or_404(Product, pk=product_id)
        root_folder, _ = Folder.objects.get_or_create(product=product, name='Root', defaults={'parent': None})
        current_folder = get_object_or_404(Folder, pk=current_folder_id) if current_folder_id else root_folder

        # Fetching the required context for the modal
        entity = get_object_or_404(Folder if entity_type == 'folder' else Document, pk=entity_id)
        if entity_type == 'folder':
            # Exclude the current entity (folder) from the list of subfolders if it's a folder
            subfolders = Folder.objects.filter(parent=current_folder).exclude(id=entity_id).order_by('name')
        else:
            subfolders = Folder.objects.filter(parent=current_folder).order_by('name')
        
        documents = Document.objects.filter(folder=current_folder)
        
        # Assemble context for rendering
        context = {
            'product': product,
            'entity': entity,
            'entity_type': entity_type,
            'folders': subfolders,
            'documents': documents,
            'current_folder': current_folder,
            'breadcrumbs': self.get_breadcrumbs(current_folder, product, root_folder)
        }

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html = render_to_string('products/move_entity_fragment.html', context, request=request)
            return JsonResponse({'html': html})
        else:
            return JsonResponse({'error': 'Invalid request type'}, status=400)
    
    def post(self, request, product_id, entity_type, entity_id, current_folder_id=None):
        # Build data for the serializer
        data = {
            'entity_ids': [int(entity_id)],  # Ensure IDs are integers
            'entity_types': [entity_type],
            'target_folder_id': int(request.data.get('target_folder_id'))
        }

        serializer = MoveEntitiesSerializer(data=data)
        if serializer.is_valid():
            target_folder = serializer.validated_data['target_folder']
            try:
                with transaction.atomic():
                    for entity_id, entity_type in zip(serializer.validated_data['entity_ids'], serializer.validated_data['entity_types']):
                        entity = get_object_or_404(Folder if entity_type == 'folder' else Document, pk=entity_id)

                        # Perform the move logic as needed
                        if entity_type == 'folder':
                            entity.parent = target_folder
                        else:
                            entity.folder = target_folder
                        entity.save()

                return Response({'success': True, 'message': 'Entities moved'}, status=status.HTTP_200_OK)
            
            except Exception as e:
                logger.error(f"Failed to move entities for product {product_id}: {str(e)}")
                return Response({'success': False, 'message': 'Failed to move entities due to a server error.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        else:
            logger.error(f"Validation errors: {serializer.errors}")
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def get_breadcrumbs(self, folder, product, root_folder):
        breadcrumbs = [{'id': root_folder.id, 'name': product.product_name}]
        ancestors = list(folder.get_ancestors(include_self=True))
        if ancestors and ancestors[0] == root_folder:
            breadcrumbs.extend([{'id': ancestor.id, 'name': ancestor.name} for ancestor in ancestors[1:]])
        else:
            breadcrumbs.extend([{'id': ancestor.id, 'name': ancestor.name} for ancestor in ancestors])
        return breadcrumbs
    

@login_required
def move_entity(request, product_id, entity_type, entity_id, current_folder_id=None):
    print("Move entity view called")
    product = get_object_or_404(Product, pk=product_id)
    entity = get_object_or_404(Folder if entity_type == 'folder' else Document, pk=entity_id)
    root_folder, _ = Folder.objects.get_or_create(product=product, name='Root', defaults={'parent': None})
    current_folder = get_object_or_404(Folder, pk=current_folder_id) if current_folder_id else root_folder
    
    
    if current_folder_id and current_folder_id != root_folder.id:
        current_folder = get_object_or_404(Folder, id=current_folder_id)
        # Get ancestors of the current folder including itself for the breadcrumbs
        folder_ancestors = list(current_folder.get_ancestors(include_self=True))
        # Replace the first item (root folder) with a custom entry for the product name
        breadcrumbs = [{'id': root_folder.id, 'name': product.product_name}]
        # Extend breadcrumbs with current folder's ancestors, skipping the first one if it's the root
        breadcrumbs.extend([{'id': folder.id, 'name': folder.name} for folder in folder_ancestors[1:]])
    else:
        current_folder = root_folder
        # Only use the product name for the root breadcrumb
        breadcrumbs = [{'id': root_folder.id, 'name': product.product_name}]

    if request.method == 'POST':
        target_folder_id = request.POST.get('target_folder_id')
        if target_folder_id == str(entity_id) and entity_type == 'folder':
            return JsonResponse({'success': False, 'message': 'Cannot move a folder into itself.'})

        target_folder = get_object_or_404(Folder, pk=target_folder_id)

        if entity_type == 'folder' and entity.parent_id == target_folder_id:
            return JsonResponse({'success': False, 'message': 'Folder is already in this location.'})
        elif entity_type == 'document' and entity.folder_id == target_folder_id:
            return JsonResponse({'success': False, 'message': 'Document is already in this folder.'})

        with transaction.atomic():
            if entity_type == 'folder':
                entity.parent = target_folder
            else:
                entity.folder = target_folder
            entity.save()
        
        redirect_url = reverse('products:product_explorer_folder', kwargs={'product_id': product_id, 'folder_id': current_folder.id})
        return JsonResponse({'success': True, 'message': 'Item moved', 'redirect': redirect_url})


    # Navigation context
    folders = Folder.objects.filter(parent=current_folder).exclude(id=entity.id if entity_type == 'folder' else None).order_by('name')
    documents = Document.objects.filter(folder=current_folder).exclude(id=entity.id if entity_type == 'document' else None).order_by('original_filename')

    context = {
        'product': product,
        'entity': entity,
        'entity_type': entity_type,
        'folders': folders,
        'documents': documents,
        'current_folder': current_folder,
        'root_folder': root_folder,
        'breadcrumbs': breadcrumbs,
    }
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = render_to_string('products/move_entity_fragment.html', context, request=request)
        return JsonResponse({'html': html})
    
    return render(request, 'products/product_explorer.html', context)


@login_required
@require_http_methods(["POST"])
def move_entities(request, product_id, current_folder_id=None):
    product = get_object_or_404(Product, pk=product_id)
    root_folder, _ = Folder.objects.get_or_create(product=product, name='Root')
    current_folder = get_object_or_404(Folder, pk=current_folder_id) if current_folder_id else root_folder


    if request.method == 'POST':
        entity_ids = request.POST.getlist('entity_ids[]')
        entity_types = request.POST.getlist('entity_types[]')
        target_folder_id = request.POST.get('target_folder_id')
        target_folder = get_object_or_404(Folder, pk=target_folder_id)

        print("Entity IDs length:", len(entity_ids), "Entity Types length:", len(entity_types), entity_types)

        if len(entity_ids) != len(entity_types):
            return JsonResponse({'success': False, 'message': 'Mismatch between entity IDs and types.'}, status=400)

        entities_moved = []
        with transaction.atomic():
            for entity_id, entity_type in zip(entity_ids, entity_types):
                if entity_type not in ['folder', 'document']:
                    continue

                model_class = Folder if entity_type == 'folder' else Document
                entity = get_object_or_404(model_class, pk=entity_id)

                if str(entity_id) == target_folder_id:
                    continue  # Skip if trying to move a folder into itself
                if entity_type == 'folder' and entity.parent_id == target_folder_id:
                    continue  # Skip if already in the target folder
                if entity_type == 'document' and entity.folder_id == target_folder_id:
                    continue  # Skip if already in the target folder

                if entity_type == 'folder':
                    entity.parent = target_folder
                else:
                    entity.folder = target_folder
                
                entity.save()
                entities_moved.append(entity_id)
        
        return JsonResponse({'success': True, 'message': f'Entities moved successfully: {entities_moved}'})

    # If GET method or other, handle accordingly
    return JsonResponse({'error': 'Invalid request method.'}, status=405)


class FolderContentView(APIView):
    
    def get(self, request, product_id, folder_id):
        product = get_object_or_404(Product, pk=product_id)
        folder = get_object_or_404(Folder, pk=folder_id, product=product)
        moving_folder_id = request.GET.get('moving_folder_id', None)

        subfolders = Folder.objects.filter(parent=folder).order_by('name')
        documents = Document.objects.filter(folder=folder)
        is_empty = not subfolders.exists() and not documents.exists()
        if moving_folder_id and moving_folder_id.isdigit():
            moving_folder_id = int(moving_folder_id)
        else:
            moving_folder_id = None

        # Determine the root folder and compute breadcrumbs
        root_folder = Folder.objects.filter(product=product, name='Root').first()
        breadcrumbs = [{'id': root_folder.id, 'name': product.product_name}]

        folder_ancestors = list(folder.get_ancestors(include_self=True))
        if folder_ancestors and folder_ancestors[0] == root_folder:
            breadcrumbs.extend([{'id': ancestor.id, 'name': ancestor.name} for ancestor in folder_ancestors[1:]])
        else:
            breadcrumbs.extend([{'id': ancestor.id, 'name': ancestor.name} for ancestor in folder_ancestors])

        context = {
            'folder': folder,
            'subfolders': subfolders,
            'documents': documents,
            'is_empty': is_empty,
            'breadcrumbs': breadcrumbs,
            'moving_folder_id': moving_folder_id
        }

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html_content = render_to_string('partials/folder_content.html', context, request=request)
            return Response({
                'html': html_content,
                'breadcrumbs': breadcrumbs
            })
        else:
            return Response(context)
