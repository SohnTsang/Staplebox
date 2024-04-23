from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Folder
from .forms import FolderForm
from products.models import Product
from .models import Folder
from django.http import JsonResponse
from django.contrib import messages  # Optional: For user feedback
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django import forms
from django.utils import timezone
from .utils import handle_item_action, clean_bins


@login_required
def folder_create(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    root_folder, created = Folder.objects.get_or_create(
        name="Root", 
        product=product, 
        defaults={'is_root': True, 'parent': None}
    )

    if not created:
        root_folder.is_root = True
        root_folder.save()

    if request.method == 'POST':
        form = FolderForm(request.POST)
        if form.is_valid():
            folder = form.save(commit=False)
            folder.product = product
            folder.created_by = request.user

            parent_id = request.POST.get('parent_id')
            if parent_id:
                folder.parent_id = parent_id
            else:
                folder.parent = root_folder

            folder.save()

            return redirect(reverse('products:product_explorer_folder', kwargs={'product_id': product_id, 'folder_id': folder.parent_id if folder.parent_id else ''}), status=303)

        else:
            messages.error(request, 'Error creating folder.')

    return redirect(reverse('products:product_explorer', kwargs={'product_id': product_id}), status=303)


@login_required
@require_http_methods(["GET", "POST"])
def edit_folder(request, product_id, folder_id):
    folder = get_object_or_404(Folder, id=folder_id, product_id=product_id)
    parent_folder_id = folder.parent_id
    if request.method == 'POST':
        form = FolderForm(request.POST, instance=folder, use_required_attribute=False)
        form.fields['parent'].widget = forms.HiddenInput()  # Hide the parent field
        if form.is_valid():
            folder.updated_at = timezone.now()
            form.save()
            # Redirect to the parent folder if it exists, otherwise go to the product's root folder view
            if parent_folder_id:
                return redirect(reverse('products:product_explorer_folder', kwargs={'product_id': product_id, 'folder_id': parent_folder_id}), status=303)
            else:
                # Assuming 'products:product_explorer' is the URL name for the root folder view
                return redirect(reverse('products:product_explorer', kwargs={'product_id': product_id}), status=303)
    else:
        form = FolderForm(instance=folder, use_required_attribute=False)
        form.fields['parent'].widget = forms.HiddenInput()  # Hide the parent field

    return render(request, 'folders/edit_folder.html', {'form': form, 'product_id': product_id, 'folder_id': folder_id})


@login_required
def ajax_get_folder_details(request, product_id, folder_id):
    folder = get_object_or_404(Folder, id=folder_id, product_id=product_id)
    data = {
        'name': folder.name,
        'parent_id': folder.parent_id if folder.parent else '',
    }
    return JsonResponse(data)


@login_required
def delete_folder(request, folder_id):
    if request.method == 'POST':
        folder = get_object_or_404(Folder, id=folder_id)
        product_id = folder.product_id  # Assuming Folder model has a 'product' field linking to Product
        parent_id = folder.parent_id if folder.parent else ''  # Capture parent ID before deletion
        
        folder.delete()
        
        # Redirect to the parent folder if it exists, or the product's root if not
        if parent_id:
            return redirect('products:product_explorer_bin', product_id=product_id)
        else:
            return redirect('products:product_explorer_bin', product_id=product_id)
    else:
        return redirect('products:product_explorer')  # Or some error handling
    

@login_required
def move_to_bin_folder(request, folder_id):
    folder = get_object_or_404(Folder, id=folder_id)
    parent_id = folder.parent_id
    bin_folder = Folder.objects.get_or_create(name="Bin", product=folder.product, is_bin=True)[0]  # Ensure a bin exists
    handle_item_action("move_to_bin", folder, bin_folder=bin_folder)
    clean_bins()
    return redirect('products:product_explorer_folder', product_id=folder.product.id, folder_id=parent_id if folder.parent else '')


@login_required
def restore_folder(request, folder_id):
    folder = get_object_or_404(Folder, id=folder_id)
    handle_item_action("restore", folder)
    return redirect('products:product_explorer_bin', product_id=folder.product.id)