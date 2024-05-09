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
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from documents.models import Document
from django.template.loader import render_to_string
from django.db import transaction
from django.views.decorators.http import require_http_methods
from partners.utils import get_partner_info
from folder.utils import clean_bins    

@login_required
def product_list(request):
    
    current_sort = request.GET.get('sort', 'updated_at')
    current_direction = request.GET.get('direction', 'asc')

    filter_type = request.GET.get('filter_type', 'product_code')  # Default to filtering by product_name
    filter_value = request.GET.get('filter_value', '')

    if 'sort' in request.GET:
        previous_sort = request.session.get('current_sort')
        # Use 'previous_direction' to remember the last sorting direction.
        previous_direction = request.session.get('current_direction', 'desc')

        # Check if the same sort field is clicked again.
        if current_sort == previous_sort:
            # If 'direction' is explicitly provided in the request, use it.
            # Otherwise, toggle based on the previous direction.
            if 'direction' in request.GET:
                current_direction = request.GET.get('direction')
            else:
                current_direction = 'asc' if previous_direction == 'desc' else 'desc'
        else:
            # For a different sort field, you might want to set a default direction or use 'asc'.
            current_direction = 'asc'

    # Save the current sort and direction in the session
    request.session['current_sort'] = current_sort
    request.session['current_direction'] = current_direction

    products_with_root = []  # A new list to hold products with their root folder ID

    if request.user.is_authenticated:
        filters = {f'{filter_type}__icontains': filter_value} if filter_value else {}
        products = Product.objects.filter(**filters).filter(user=request.user).order_by(f'{"" if current_direction == "asc" else "-"}{current_sort}')
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

        page_number = request.GET.get('page', 1)  # Get the page number from the query parameters
        paginator = Paginator(products_with_root, 13)  # Show 10 products per page. Adjust as needed.

        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            page_obj = paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of results.
            page_obj = paginator.page(paginator.num_pages)

        context = {
            'products_with_root': products_with_root,
            'current_sort': current_sort,
            'current_direction': current_direction,
            'filter_value': filter_value,
            'filter_type': filter_type,
            'page_obj': page_obj,
            'hide_top_bar': True,
            'active_page': 'Products',
        }

    else:
        products_with_root = []
        context = {
            'products_with_root': products_with_root,
            'current_sort': current_sort,
            'current_direction': current_direction,
            'filter_value': filter_value,
            'filter_type': filter_type,
            'hide_top_bar': True,
            'active_page': 'Products',
        }

    return render(request, 'products/product_list.html', context)


@login_required
def create_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, user=request.user)
        if form.is_valid():
            product = form.save(commit=False)
            product.user = request.user
            product.save()
            messages.success(request, 'Product created successfully!')
            return redirect('products:product_list')
    else:
        form = ProductForm(user=request.user)
    return render(request, 'products/product_form.html', {'form': form})


@login_required
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk, user=request.user)

    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product updated successfully!')
            return redirect('products:product_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'products/product_form.html', {'form': form})


@login_required
def product_explorer(request, product_id, folder_id=None):
    user = request.user
    partner_info = get_partner_info(user)

    product = get_object_or_404(Product, id=product_id)
    root_folder, _ = Folder.objects.get_or_create(product=product, name='Root', defaults={'parent': None})

    if folder_id and folder_id != root_folder.id:
        current_folder = get_object_or_404(Folder, id=folder_id)
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

    subfolders = Folder.objects.filter(parent=current_folder).order_by('name')
    documents = Document.objects.filter(folder=current_folder).order_by('original_filename')
    document_types = DocumentType.objects.all()

    for document in documents:
        document.latest_version = document.versions.latest('created_at') if document.versions.exists() else None
        document.created_at = document.created_at  # Adjust as per your model
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
    }

    return render(request, 'products/product_explorer.html', context)


@login_required
def product_explorer_bin(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
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
    }
    clean_bins()
    return render(request, 'products/product_explorer.html', context)


@login_required
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk, user=request.user)
    if request.method == 'POST':
        # Optional: Handle related objects (like folders) here if needed
        # For example, delete or reassign related folders
        Folder.objects.filter(product=product).delete()  # Adjust as necessary

        product.delete()
        return redirect('products:product_list')  # Adjust the redirect as needed
    else:
        return redirect('products:product_list')  # Adjust the redirect as needed

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


@login_required
def move_entity(request, product_id, entity_type, entity_id, current_folder_id=None):
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


@login_required
def folder_content(request, product_id, folder_id, moving_folder_id=None):
    product = get_object_or_404(Product, pk=product_id)
    folder = get_object_or_404(Folder, pk=folder_id, product=product)
    subfolders = Folder.objects.filter(parent=folder).order_by('name')
    documents = Document.objects.filter(folder=folder)
    is_empty = not subfolders.exists() and not documents.exists()
    moving_folder_id = request.GET.get('moving_folder_id', None)

    if moving_folder_id and moving_folder_id.isdigit():
        moving_folder_id = int(moving_folder_id)
    else:
        moving_folder_id = None

    # Determine the root folder and compute breadcrumbs
    root_folder = Folder.objects.filter(product=product, name='Root').first()

    # Initial breadcrumb for the product's root directory
    breadcrumbs = [{'id': root_folder.id, 'name': product.product_name}]

    # Include ancestors, ensuring no duplication of the root entry
    folder_ancestors = list(folder.get_ancestors(include_self=True))
    if folder_ancestors and folder_ancestors[0] == root_folder:
        # If the root folder is the first ancestor, skip adding it again
        breadcrumbs.extend([{'id': ancestor.id, 'name': ancestor.name} for ancestor in folder_ancestors[1:]])
    else:
        # Otherwise, add all ancestors
        breadcrumbs.extend([{'id': ancestor.id, 'name': ancestor.name} for ancestor in folder_ancestors])

    context = {
        'folder': folder,
        'subfolders': subfolders,
        'documents': documents,
        'is_empty': is_empty,
        'breadcrumbs': breadcrumbs,
        'moving_folder_id': moving_folder_id  # Add this to context
    }

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html_content = render_to_string('partials/folder_content.html', context, request=request)
        return JsonResponse({
            'html': html_content,
            'breadcrumbs': breadcrumbs
        })
    else:
        return render(request, 'partials/folder_content.html', context)