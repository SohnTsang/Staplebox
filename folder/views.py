from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Folder
from .forms import FolderForm
from products.models import Product
from .models import Folder
from documents.models import Document
from django.http import JsonResponse


@login_required
def folder_explorer(request, product_id, folder_id=None):
    product = get_object_or_404(Product, id=product_id)
    current_folder = get_object_or_404(Folder, id=folder_id) if folder_id else None
    subfolders = Folder.objects.filter(parent=current_folder, product=product)
    documents = Document.objects.filter(folder=current_folder)

    if current_folder:
        breadcrumbs = current_folder.get_ancestors()
    else:
        breadcrumbs = []

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        response_data = {
            'folders': [{'id': f.id, 'name': f.name} for f in subfolders],
            'documents': [{'id': d.id, 'name': d.file.name.split('/')[-1]} for d in documents],
            'currentFolderName': current_folder.name if current_folder else "Root",
            'productName': product.product_name,
            'breadcrumbs': [{'id': b.id, 'name': b.name} for b in breadcrumbs],
        }
        return JsonResponse(response_data)

    context = {
        'product': product,
        'current_folder': current_folder,
        'subfolders': subfolders,
        'documents': documents,
        'breadcrumbs': breadcrumbs,
    }
    return render(request, 'folders/folder_contents.html', context)

@login_required
def folder_create(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    # Ensure there is a root folder for the product but don't recreate it if it already exists.
    root_folder, created = Folder.objects.get_or_create(
        name="Root", 
        product=product, 
        defaults={'is_root': True, 'parent': None}
    )
    
    if not created:
        # If the root folder was not created this time (i.e., it already exists), ensure it's marked as root.
        root_folder.is_root = True
        root_folder.save()

    if request.method == 'POST':
        form = FolderForm(request.POST)
        if form.is_valid():
            folder = form.save(commit=False)
            folder.product = product
            
            # Assign the parent folder if it's provided, otherwise set to root
            parent_id = request.POST.get('parent_id', None)
            if parent_id:
                try:
                    folder.parent_id = parent_id
                except Folder.DoesNotExist:
                    return JsonResponse({'success': False, 'errors': 'Invalid parent folder.'}, status=400)
            else:
                # Optionally, automatically set root as the parent if no parent is specified
                folder.parent = root_folder

            folder.save()
            return JsonResponse({'success': True, 'folderId': folder.id, 'folderName': folder.name}, status=201)
        else:
            return JsonResponse({'success': False, 'errors': form.errors.as_json()}, status=400)
    else:
        form = FolderForm()
        return render(request, 'folder/folder_form.html', {'form': form, 'product': product})

@login_required
def delete_folder(request, folder_id):
    if request.method == 'POST':
        folder = get_object_or_404(Folder, id=folder_id)
        folder.delete()
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)