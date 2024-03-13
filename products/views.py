# products/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Product
from .forms import ProductForm
from users.models import UserProfile
from folder.models import Folder  # Assuming the Folder model is in the folder app
from django.http import JsonResponse
from django.db.models import Q
from django.urls import reverse
from document_types.models import DocumentType
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from documents.models import Document


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
        paginator = Paginator(products_with_root, 10)  # Show 10 products per page. Adjust as needed.

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
        }

    else:
        products_with_root = []
        context = {
            'products_with_root': products_with_root,
            'current_sort': current_sort,
            'current_direction': current_direction,
            'filter_value': filter_value,
            'filter_type': filter_type,
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
    documents = Document.objects.filter(folder=current_folder).order_by('created_at')
    document_types = DocumentType.objects.all()

    context = {
        'product': product,
        'root_folder': root_folder,
        'current_folder': current_folder,
        'subfolders': subfolders,
        'documents': documents,
        'document_types': document_types,
        'breadcrumbs': breadcrumbs,
    }

    return render(request, 'products/product_explorer.html', context)


@login_required
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk, user=request.user)
    if request.method == 'POST':
        # Optional: Handle related objects (like folders) here if needed
        # For example, delete or reassign related folders
        Folder.objects.filter(product=product).delete()  # Adjust as necessary

        product.delete()
        return redirect('home')  # Adjust the redirect as needed
    else:
        return redirect('product_detail', pk=pk)  # Redirect to a safe page, adjust as needed

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