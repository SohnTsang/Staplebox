# views.py
import json, os
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render
from .models import Product, Folder, Document, AccessPermission
from partners.models import Partnership  
from users.models import UserProfile
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist
from django.core.cache import cache
from django.db.models import Q
from collections import defaultdict
from django.db.models import Prefetch
from django.urls import reverse
from .forms import AccessPermissionForm
from django.db import transaction





@login_required
def get_access_details(request, product_id):
    #try:
    # Query AccessPermission instances related to the given product_id
    access_permissions = AccessPermission.objects.filter(
            Q(product_id=product_id) |
            Q(folder__product_id=product_id) |
            Q(document__folder__product_id=product_id)
        ).distinct().select_related('partner2', 'folder', 'document')        

    access_details = []
    for access in access_permissions:
        if access.document:
            document_name = os.path.basename(access.document.file.name)  # Using os.path.basename to get the file name
            access_level = f'Document: {document_name}'
        elif access.folder:
            access_level = f'Folder: {access.folder.name}'
        else:
            access_level = 'Product Access'

        access_details.append({
            'id': access.id,
            'partnerName': access.partner2.username,
            'accessLevel': access_level
        })
    data = {'accessDetails': access_details}

    return JsonResponse(data)



def initialize_folder_hierarchy(folder, structure, is_root=True):
    """
    Initialize the folder structure, including all ancestors, and return the structure of the current folder.
    """
    if not folder:
        return structure
    
    current_structure = structure
    ancestors = folder.get_ancestors(include_self=True)
    for ancestor in ancestors[:-1]:  # Exclude the last item for special handling
        if ancestor.id not in current_structure:
            current_structure[ancestor.id] = {
                'name': ancestor.name,
                'documents': [],
                'subfolders': defaultdict(dict),
                'is_root': is_root
            }
        current_structure = current_structure[ancestor.id]['subfolders']
        is_root = False  # Only the first ancestor is considered root

    # Handle the last item (the current folder)
    current_folder = ancestors[-1]
    if current_folder.id not in current_structure:
        current_structure[current_folder.id] = {
            'name': current_folder.name,
            'documents': [],
            'subfolders': defaultdict(dict),
            'is_root': is_root
        }
    
    return current_structure[current_folder.id]

def convert_defaultdict_to_dict(d):
    """
    Recursively convert a defaultdict to a regular dict.
    This function is crucial for ensuring the template can iterate over the data.
    """
    if isinstance(d, defaultdict):
        d = {k: convert_defaultdict_to_dict(v) for k, v in d.items()}
    elif isinstance(d, dict):  # Additional check to recursively convert nested defaultdicts
        d = {k: convert_defaultdict_to_dict(v) for k, v in d.items()}
    return d

@login_required
def view_access(request):
    user = request.user
    # Fetch permissions with optimized queries for folders and documents
    permissions = AccessPermission.objects.filter(
        partner2=user
    ).prefetch_related(
        Prefetch('product'),
        Prefetch('folder'),
        Prefetch('document')
    ).distinct()

    product_structure = defaultdict(lambda: {
        'name': '',
        'partner1': '',
        'folders': defaultdict(lambda: {  # Nested defaultdict for folders
            'name': '',
            'documents': [],
            'subfolders': defaultdict(dict),
            'is_root': False
        }),
        'documents': [],
        'has_subfolders': False
    })

    for perm in permissions:
        product_key = perm.product.id if perm.product else 'general'
        product_entry = product_structure[product_key]

        if perm.product:
            product_entry['name'] = perm.product.product_name
            product_entry['partner1'] = perm.partner1.username if perm.partner1 else 'N/A'

        if perm.folder:
            # Initialize folder hierarchy
            folder_struct = initialize_folder_hierarchy(perm.folder, product_entry['folders'])
        
        if perm.document:
            # Assuming Document model has 'folder' ForeignKey to Folder
            # If document is directly associated with a permission, find its folder
            document_folder = perm.document.folder
            document_name = os.path.basename(perm.document.file.name)
            document_id = perm.document.id
            download_url = reverse('documents:download_document', kwargs={'document_id': document_id})
            document_data = {
                'name': os.path.basename(perm.document.file.name),
                'id': document_id,
                'download_url': download_url  # Add this line to include the download URL
            }

            if document_folder:
        # If document has an associated folder, ensure it's initialized in product_structure
                folder_struct = initialize_folder_hierarchy(document_folder, product_entry['folders'])
                folder_struct['documents'].append({
                    'name': document_name,
                    'id': document_id,
                    'download_url': download_url  # Optional: include if you prefer to pass URLs directly
                })
            else:
                # Document without a folder gets added directly under the product
                product_entry['documents'].append({
                    'name': document_name,
                    'id': document_id,
                    'download_url': download_url
                })

    products_structure = convert_defaultdict_to_dict(product_structure)
    context = {'products_structure': products_structure}
    return render(request, 'access_control/view_access.html', context)


@login_required
def manage_access(request, product_id):
    user = request.user
    product = get_object_or_404(Product, id=product_id)

    permissions = AccessPermission.objects.filter(product=product).select_related('partner2', 'folder', 'document')
    partners_with_access = []

    for permission in permissions:
        access_detail = f"{permission.partner2.username} - Prod: {permission.product.product_name}"
        if permission.folder:
            access_detail += f", Folder: {permission.folder.name}"
        if permission.document:
            access_detail += f", Doc: {permission.document.display_filename}"
        partners_with_access.append(access_detail)

    # Ensure the user requesting this page is the product owner
    if product.user != user:
        messages.error(request, "You are not authorized to manage access for this product.")
        return redirect('home')  # Update with your actual redirect

    form = AccessPermissionForm(request.POST or None, user=user, product_id=product_id)
    # Processing form submission (grant access)
    if request.method == 'POST' and form.is_valid():
        messages_list = []
        action = request.POST.get('action')
        with transaction.atomic():
            if action == 'remove_access':
                # Handle the removal of selected permissions
                permissions_to_remove = form.cleaned_data.get('remove_permissions', [])
                for permission in permissions_to_remove:
                    permission.delete()
                messages.success(request, "Access removed successfully.")
            
            elif action == 'grant_access':
                # Extracting selected partner IDs, folder IDs, and document IDs from form.cleaned_data
                    partners = form.cleaned_data['partners']  # This should be a queryset of User instances.
                    folder_ids = request.POST.getlist('folders')
                    document_ids = request.POST.getlist('documents')
                    granting_product_level_access = not folder_ids and not document_ids

                    for partner in partners:
                        if granting_product_level_access:
                            message = grant_product_access(user, partner, product)
                        else:
                            for folder_id in folder_ids:
                                folder = get_object_or_404(Folder, id=folder_id)
                                message = grant_folder_or_document_access(user, partner, product, folder=folder)
                                messages_list.append(message)
                            for document_id in document_ids:
                                document = get_object_or_404(Document, id=document_id)
                                message = grant_folder_or_document_access(user, partner, product, document=document)
                                messages_list.append(message)
                        
                        # Append and display messages for each partner processed
                        messages.info(request, message)

                # Redirect to avoid re-posting form data
            return redirect('access_control:manage_access', product_id=product_id)
            
    else:
        form = AccessPermissionForm(user=request.user, product_id=product_id)
        
    # Fetching active partnerships, folders, and documents as before for display
    active_partnerships = Partnership.objects.filter(
        Q(partner1=user) | Q(partner2=user),
        is_active=True
    ).distinct()

    active_partners = set()
    for partnership in active_partnerships:
        if partnership.partner1 == user:
            active_partners.add(partnership.partner2)
        else:
            active_partners.add(partnership.partner1)

    folders = Folder.objects.filter(product=product, parent__isnull=True)
    documents = Document.objects.filter(folder__in=folders)
    folders_data = [{'folder': folder, 'documents': documents.filter(folder=folder)} for folder in folders]

    context = {
        'product': product,
        'partners': list(active_partners),
        'folders': folders,
        'folders_data': folders_data,
        'partners_with_access': partners_with_access,
        'form': form,  # Include the form in the context
    }

    return render(request, 'access_control/manage_access.html', context)


def grant_product_access(user, partner, product):
    # First, remove any specific folder/document-level permissions.
    AccessPermission.objects.filter(
        product=product, 
        partner1=user, 
        partner2=partner
    ).exclude(
        folder__isnull=True, 
        document__isnull=True
    ).delete()

    # Next, get or create a single product-level permission.
    permission, created = AccessPermission.objects.get_or_create(
        product=product, 
        partner1=user, 
        partner2=partner,
        defaults={'folder': None, 'document': None}
    )

    # If a new product-level permission was created, indicate so.
    if created:
        return f"Granted {partner.username} access to the entire product: {product.product_name}."
    else:
        # If the permission already existed, there's nothing more to do.
        return f"{partner.username} already had access to the entire product: {product.product_name}."
    
    return message

def grant_folder_or_document_access(user, partner, product, folder=None, document=None):
    if AccessPermission.objects.filter(product=product, partner2=partner, folder__isnull=True, document__isnull=True).exists():
        return f"{partner.username} already has access to the entire product: {product.product_name}, which includes all folders and documents."

    if folder:
        _, created = AccessPermission.objects.get_or_create(product=product, partner1=user, partner2=partner, folder=folder)
        return f"Granted {partner.username} access to folder: {folder.name} in product: {product.product_name}." if created else f"{partner.username} already has access to folder: {folder.name}."
    elif document:
        _, created = AccessPermission.objects.get_or_create(product=product, partner1=user, partner2=partner, document=document)
        return f"Granted {partner.username} access to document: {document.display_filename} in product: {product.product_name}." if created else f"{partner.username} already has access to document: {document.display_filename}."















def grant_access_to_product(user, partner, product_id):
    product = get_object_or_404(Product, pk=product_id)
    # Ensure a Product instance is used for the 'product' parameter
    AccessPermission.objects.get_or_create(partner1=user, partner2=partner, product=product)
    
    # Keep track of root folder IDs to avoid duplicates
    root_folder_ids = set()
    
    # Print the hierarchical structure of each folder in the product
    for folder in product.folders.all():
        # Check if the folder is a root folder and if its ID is not already processed
        if folder.is_root and folder.id not in root_folder_ids:
            print_hierarchical_structure(folder)
            root_folder_ids.add(folder.id)
        
        # Grant access to each folder and its contents
        grant_access_to_folder(user, partner, folder, product)

def fetch_all_document_ids_within_folder(folder_id):
    """
    Recursively fetch all document IDs within a folder, including its subfolders.
    """
    folder = Folder.objects.get(id=folder_id)
    document_ids = list(folder.documents.values_list('id', flat=True))
    for subfolder in folder.subfolders.all():
        document_ids.extend(fetch_all_document_ids_within_folder(subfolder.id))
    return document_ids

def grant_specific_access(user, partner, product_id, folder_ids, document_ids):
    printed_folders = set()
    product = Product.objects.get(id=product_id)
    printed_folders = set()  # To keep track of folders that have been printed

    for folder_id in folder_ids:
        document_ids.update(fetch_all_document_ids_within_folder(folder_id))
    
    root_folder_access_granted = any(Folder.objects.filter(id=folder_id, product=product, is_root=True).exists() for folder_id in folder_ids)

    if root_folder_access_granted:
        # If access to the root folder is granted, grant access to the whole product
        grant_access_to_product(user, partner, product_id)
    else:
        # If specific folders are specified, grant access to them and their hierarchy
        if folder_ids:
            for folder_id in folder_ids:
                folder = Folder.objects.get(id=folder_id, product=product)
                # Grant access up the hierarchy from the specified folder
                grant_access_upwards(user, partner, folder, product)
                # Grant access downwards from the specified folder
                grant_access_downwards(user, partner, folder)

                # Print hierarchical structure if the folder has not been printed before
                if folder not in printed_folders:
                    print_hierarchical_structure(folder, printed_folders)

                    printed_folders.add(folder)
                
        # If specific documents are specified, grant access to them
        if document_ids:
            for document_id in document_ids:
                document = Document.objects.get(id=document_id)
                if document.folder:
                    # Grant access to the document's folder and up the hierarchy
                    grant_access_upwards(user, partner, document.folder, product)
                    
                # Grant access to the document itself
                AccessPermission.objects.get_or_create(partner1=user, partner2=partner, document=document, product=product)

    # Grant access to specific documents
    if document_ids:
        for document_id in document_ids:
            document = Document.objects.get(id=document_id)
            # Grant access to the document's folder and up the hierarchy.
            if document.folder:
                grant_access_upwards(user, partner, document.folder, product)
            # Grant access to the document itself.
            AccessPermission.objects.get_or_create(partner1=user, partner2=partner, document=document, product=product)


def grant_access_upwards(user, partner, folder, product):
    # Recursively grant access to the folder and its ancestors.
    current_folder = folder
    while current_folder:
        AccessPermission.objects.get_or_create(partner1=user, partner2=partner, folder=current_folder, product=product)
        current_folder = current_folder.parent

def grant_access_downwards(user, partner, folder):
    # Recursively grant access to subfolders and their documents.
    AccessPermission.objects.get_or_create(partner1=user, partner2=partner, folder=folder, product=folder.product)
    for document in folder.documents.all():
        AccessPermission.objects.get_or_create(partner1=user, partner2=partner, document=document, product=folder.product)
    for subfolder in folder.subfolders.all():
        grant_access_downwards(user, partner, subfolder)

def grant_access_to_folder(user, partner, folder, product):
    # Create access permission for the folder
    AccessPermission.objects.get_or_create(partner1=user, partner2=partner, folder=folder, product=product)
    
    # Fetch and create access permissions for all documents within the folder
    document_ids = fetch_all_document_ids_within_folder(folder.id)
    for doc_id in document_ids:
        document = Document.objects.get(id=doc_id)
        AccessPermission.objects.get_or_create(partner1=user, partner2=partner, document=document, product=product)
        
        
    
    # Recursively grant access to subfolders
    for subfolder in folder.subfolders.all():
        grant_access_to_folder(user, partner, subfolder, product)

@csrf_exempt
@require_POST
def remove_access(request, access_id):
    try:
        access_permission = AccessPermission.objects.get(id=access_id, partner1=request.user)
        access_permission.delete()
        return JsonResponse({'success': True, 'message': 'Access successfully removed.'})
    except AccessPermission.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Access permission not found or you do not have permission to remove it.'}, status=404)
    

def print_hierarchical_structure(folder, printed_folders=None, indent=0, include_ancestors=True):
    """
    Print the hierarchical structure of a folder with proper indentation, including its ancestors.
    Avoids infinite loops by keeping track of printed folders.
    """
    if printed_folders is None:
        printed_folders = set()

    # Optionally include ancestors in the printout
    if include_ancestors:
        ancestors = folder.get_ancestors(include_self=False)
        for ancestor in ancestors:
            if ancestor.id not in printed_folders:
                print(" " * indent + f"Folder: {ancestor.name}")
                printed_folders.add(ancestor.id)
                indent += 2  # Increase indent for the next level

    # Now handle the current folder as before
    if folder.id in printed_folders:
        return
    printed_folders.add(folder.id)

    # Print the current folder name with appropriate indentation
    print(" " * indent + f"Folder: {folder.name}")

    # Print documents within the folder
    for document in folder.documents.all():
        print(" " * (indent + 2) + f"Document: {document.file_name}")

    # Recursively print subfolders
    for subfolder in folder.subfolders.all():
        print_hierarchical_structure(subfolder, printed_folders, indent=indent + 2, include_ancestors=False)

