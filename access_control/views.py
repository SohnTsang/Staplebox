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

    displayed_permissions = set()
    partners_with_access = set()

    for permission in permissions:
        # Simplify by focusing on the highest level of access granted
        if permission.folder is None and permission.document is None:
            # Product-level access
            access_detail = f"{permission.partner2.username} - Prod: {permission.product.product_name}"
        elif permission.folder and not permission.folder.is_root:
            # Specific folder access (non-root)
            access_detail = f"{permission.partner2.username} - Prod: {permission.product.product_name}, Folder: {permission.folder.name}"
        elif permission.document:
            # Document access, ensuring it's not redundant with folder or product-level access
            access_detail = f"{permission.partner2.username} - Prod: {permission.product.product_name}, Doc: {permission.document.display_filename}"
        else:
            continue  # Skip if it's root access or otherwise handled
        
        partners_with_access.add(access_detail)  # Add unique access details

    partners_with_access = list(partners_with_access)  # Convert set back to list for template rendering

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
                permissions_to_remove = form.cleaned_data.get('remove_permissions', [])
                removed_count = 0

                if permissions_to_remove:
                    for permission in permissions_to_remove:
                        permission.delete()
                        removed_count += 1

                    if removed_count > 0:
                        # If at least one permission was successfully removed
                        messages.success(request, f"Access removed successfully for {removed_count} items.")
                    else:
                        # If the list was not empty, but no permissions were actually removed
                        messages.error(request, "Could not remove access. Please try again.")
                else:
                    # If no permissions were selected for removal
                    messages.info(request, "No changes were made. Please select access permissions for removal.")

            
            elif action == 'grant_access':
                # Extracting selected partner IDs, folder IDs, and document IDs from form.cleaned_data
                    partners = form.cleaned_data['partners']  # This should be a queryset of User instances.
                    folder_ids = request.POST.getlist('folders')
                    folders = Folder.objects.filter(id__in=folder_ids)
                    root_folder_selected = folders.filter(is_root=True).exists()
                    document_ids = request.POST.getlist('documents')
                    granting_product_level_access = not folder_ids and not document_ids or root_folder_selected
                    granted_new_access = False
                    redundant_access = False

                    for partner in partners:
                        if granting_product_level_access:
                            if grant_product_access(user, partner, product):
                                granted_new_access = True
                            else:
                                redundant_access = True
                        else:
                            for folder_id in folder_ids:
                                folder = get_object_or_404(Folder, id=folder_id)
                                if grant_folder_or_document_access(user, partner, product, folder=folder):
                                    granted_new_access = True
                                else:
                                    redundant_access = True
                            for document_id in document_ids:
                                document = get_object_or_404(Document, id=document_id)
                                if grant_folder_or_document_access(user, partner, product, document=document):
                                    granted_new_access = True
                                else:
                                    redundant_access = True

                    if granted_new_access:
                        messages.success(request, "Access granted successfully.")
                    elif redundant_access:
                        messages.info(request, "No new access was granted. Existing access was sufficient.")
                    else:
                        messages.warning(request, "No access changes were made. Please select partners and items for granting access.")

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
    _, created = AccessPermission.objects.get_or_create(
        product=product, 
        partner1=user, 
        partner2=partner,
        defaults={'folder': None, 'document': None}
    )
    # If a new product-level permission was created, indicate so.
    if created:
        AccessPermission.objects.filter(product=product, partner2=partner).exclude(id=_.id).delete()
    return created
    

def grant_folder_or_document_access(user, partner, product, folder=None, document=None):
    # Check for existing product-level access.
    product_access_exists = AccessPermission.objects.filter(
        product=product, partner2=partner, folder__isnull=True, document__isnull=True
    ).exists()

    if product_access_exists:
        # Product-level access already exists, no need to grant lower-level access.
        return False

    if folder:
        # If granting access to the "Root" or product-level access is being granted.
        if folder.is_root:
            return grant_product_access(user, partner, product)
        
        # If granting access to a non-root folder, remove access to subfolders and documents within it.
        AccessPermission.objects.filter(product=product, partner2=partner, folder__in=folder.subfolders.all()).delete()
        AccessPermission.objects.filter(product=product, partner2=partner, document__folder=folder).delete()

        # Ensure no higher-level access exists before granting folder access.
        current_folder = folder.parent
        while current_folder:
            if AccessPermission.objects.filter(product=product, partner2=partner, folder=current_folder).exists():
                return False  # Higher-level access exists.
            current_folder = current_folder.parent

        _, created = AccessPermission.objects.get_or_create(product=product, partner1=user, partner2=partner, folder=folder)
        return created

    if document:
        # Check for existing product-level or folder access.
        if AccessPermission.objects.filter(product=product, partner2=partner, folder=document.folder).exists():
            return False  # Folder-level access exists.
        
        _, created = AccessPermission.objects.get_or_create(product=product, partner1=user, partner2=partner, document=document)
        return created

    return False
