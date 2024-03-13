from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Folder
from .forms import FolderForm
from products.models import Product
from .models import Folder
from documents.models import Document
from django.http import JsonResponse
from django.contrib import messages  # Optional: For user feedback
from django.urls import reverse



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

            parent_id = request.POST.get('parent_id')
            if parent_id:
                folder.parent_id = parent_id
            else:
                folder.parent = root_folder

            folder.save()

            return redirect(reverse('products:product_explorer_folder', kwargs={'product_id': product_id, 'folder_id': folder.parent_id if folder.parent_id else ''}))

        else:
            print(form.errors)
            messages.error(request, 'Error creating folder.')

    return redirect(reverse('products:product_explorer', kwargs={'product_id': product_id}))


@login_required
def delete_folder(request, folder_id):
    if request.method == 'POST':
        folder = get_object_or_404(Folder, id=folder_id)
        product_id = folder.product_id  # Assuming Folder model has a 'product' field linking to Product
        parent_id = folder.parent_id if folder.parent else ''  # Capture parent ID before deletion
        
        folder.delete()
        
        # Redirect to the parent folder if it exists, or the product's root if not
        if parent_id:
            return redirect('products:product_explorer_folder', product_id=product_id, folder_id=parent_id)
        else:
            return redirect('products:product_explorer', product_id=product_id)
    else:
        return redirect('products:product_explorer')  # Or some error handling