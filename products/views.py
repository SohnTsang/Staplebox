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

@login_required
def product_list(request):
    
    current_sort = request.GET.get('sort', 'product_code')
    current_direction = request.GET.get('direction', 'asc')
    sorting_action = request.GET.get('sorting_action', 'no')

    filter_type = request.GET.get('filter_type', 'product_code')  # Default to filtering by product_name
    filter_value = request.GET.get('filter_value', '')

    

    # Toggle direction if the same sort field is requested again
    if 'sort' in request.GET and sorting_action == 'yes':
        previous_sort = request.session.get('current_sort', None)
        previous_direction = request.session.get('current_direction', 'asc')

        if current_sort == previous_sort:
            current_direction = 'desc' if previous_direction == 'asc' else 'asc'
        else:
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

        context = {
            'products_with_root': products_with_root,
            'current_sort': current_sort,
            'current_direction': current_direction,
            'filter_value': filter_value,
            'filter_type': filter_type,
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
    document_types = DocumentType.objects.all()  # Fetch all document types
    product = get_object_or_404(Product, id=product_id)
    # Ensure there is a default "Root" folder for each product
    root_folder, created = Folder.objects.get_or_create(product=product, name='Root', defaults={'parent': None})

    if folder_id is not None and folder_id != root_folder.id:
        current_folder = get_object_or_404(Folder, id=folder_id, product=product)
    else:
        current_folder = root_folder

    folder_id = request.GET.get('folderId')

    # If no specific folder ID is provided, redirect to the root folder page
    if not folder_id:
        return redirect(
            f"{reverse('product_explorer', kwargs={'product_id': product.id})}?folderId={root_folder.id}")

    subfolders = Folder.objects.filter(parent=current_folder).order_by('name')

    # Generate breadcrumbs
    breadcrumbs = []
    temp_folder = current_folder
    while temp_folder and temp_folder != root_folder:
        breadcrumbs.insert(0, {'name': temp_folder.name, 'id': temp_folder.id})
        temp_folder = temp_folder.parent

    # Modify here to avoid adding 'Root' twice when already in 'Root'
    if current_folder != root_folder:
        breadcrumbs.insert(0, {'name': 'Root', 'id': root_folder.id})

    # Insert the root folder at the beginning of the breadcrumbs
    breadcrumbs.insert(0, {'name': 'Root', 'id': root_folder.id})

    return render(request, 'products/product_explorer.html', {
        'product': product,
        'current_folder': current_folder,
        'subfolders': subfolders,
        'breadcrumbs': breadcrumbs,
        'root_folder_id': root_folder.id,  # Pass the root folder's ID to the template
        'document_types': document_types,
    })


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