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




@login_required
def get_access_details(request, product_id):
    #try:
    # Query AccessPermission instances related to the given product_id
    access_permissions = AccessPermission.objects.filter(
            Q(product_id=product_id) |
            Q(folder__product_id=product_id) |
            Q(document__folder__product_id=product_id)
        ).distinct().select_related('importer', 'folder', 'document')        

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
            'partnerName': access.importer.username,
            'accessLevel': access_level
        })
    data = {'accessDetails': access_details}

    return JsonResponse(data)


def initialize_folder_hierarchy(folder, structure):
    """
    Recursively initialize the folder structure from the bottom up.
    """
    # Base case: if there's no folder, simply return
    if not folder:
        return

    # Initialize the folder in the structure if not already present
    if folder.id not in structure:
        structure[folder.id] = {
            'name': folder.name,
            'documents': [],
            'subfolders': defaultdict(dict)  # Ensure subfolders are always initialized as a defaultdict
        }

    # Recursively initialize the parent folder
    if folder.parent:
        # Ensure the parent folder is correctly initialized in the structure
        if folder.parent.id not in structure:
            structure[folder.parent.id] = {
                'name': folder.parent.name,
                'documents': [],
                'subfolders': defaultdict(dict)
            }
        # Now safely call the recursion with the guaranteed 'subfolders' key
        initialize_folder_hierarchy(folder.parent, structure[folder.parent.id]['subfolders'])

        # Ensure the current folder is listed under its parent's subfolders
        structure[folder.parent.id]['subfolders'][folder.id] = structure[folder.id]


@login_required
def view_access(request):
    user = request.user
    # Fetch permissions with optimized queries for folders and documents
    permissions = AccessPermission.objects.filter(
        importer=user
    ).prefetch_related(
        Prefetch('product'),
        Prefetch('folder', queryset=Folder.objects.prefetch_related('subfolders', 'documents')),
        Prefetch('document')
    ).distinct()


    # Initial empty structure for organizing products, folders, and documents
    product_structure = defaultdict(lambda: {
        'name': '',
        'exporter': '',
        'folders': {},
        'documents': [],
    })

    for perm in permissions:
        product_key = perm.product.id if perm.product else 'general'
        product_entry = product_structure[product_key]

        if perm.product:
            product_entry['name'] = perm.product.product_name
            product_entry['exporter'] = perm.exporter.username if perm.exporter else 'N/A'

        if perm.folder:
            
            # Ensure all ancestors are present in the structure
            initialize_folder_hierarchy(perm.folder, product_entry['folders'])

            if perm.document:
                # Append the document to the relevant folder
                folder_id = perm.folder.id
                document_name = os.path.basename(perm.document.file.name)
                product_entry['folders'][folder_id]['documents'].append(document_name)

        elif perm.document and not perm.folder:
            # Handle orphan documents not associated with a folder
            document_name = os.path.basename(perm.document.file.name)
            product_entry['documents'].append(document_name)

    context = {'products_structure': dict(product_structure)}

    return render(request, 'access_control/view_access.html', context)


@login_required
def manage_access(request, product_id):
    user = request.user
    product = get_object_or_404(Product, id=product_id)

    # Ensure the user requesting this page is the product owner
    if product.user != user:
        messages.error(request, "You are not authorized to manage access for this product.")
        return redirect('products/product_form.html')  # Replace with your actual redirect destination

    # Fetching active partnerships where the current user is the exporter
    active_partnerships = Partnership.objects.filter(exporter=user, is_active=True)

    # Extracting importers from those active partnerships
    active_partners = [partnership.importer for partnership in active_partnerships]

    # Fetch folders and documents related to the product
    folders = Folder.objects.filter(product=product)
    documents = Document.objects.filter(folder__in=folders)

    # Preparing folders and their documents for the template
    folders_data = [{'folder': folder, 'documents': documents.filter(folder=folder)} for folder in folders]

    context = {
        'product': product,
        'partners': active_partners,
        'folders_data': folders_data,
    }

    return render(request, 'access_control/manage_access.html', context)


@csrf_exempt
@require_POST
def grant_access(request):
    data = json.loads(request.body.decode('utf-8'))
    product_id = int(data.get('product_id'))
    partner_ids = [int(id) for id in data.get('partners', [])]
    folder_ids = set(int(id) for id in data.get('folders', []))
    document_ids = set(int(id) for id in data.get('documents', []))
    product = get_object_or_404(Product, id=product_id, user=request.user)
    if product.user != request.user:
        return JsonResponse({"error": "Unauthorized to grant access for this product."}, status=403)

    for partner_id in partner_ids:
        partner = get_object_or_404(User, id=partner_id)
        # When granting access to the entire product and its hierarchy
        if not folder_ids and not document_ids:
            grant_access_to_product(request.user, partner, product_id)
        else:
            # Specific access grants
            print(request.user, partner, product_id, folder_ids, document_ids)
            grant_specific_access(request.user, partner, product_id, folder_ids, document_ids)
            
            
    return JsonResponse({"success": True, "message": "Access granted successfully."})

def grant_access_to_product(user, partner, product_id):
    product = get_object_or_404(Product, pk=product_id)
    AccessPermission.objects.get_or_create(exporter=user, importer=partner, product=product)
    for folder in product.folders.all():
        grant_access_to_folder(user, partner, folder, product_id)

def grant_specific_access(user, partner, product_id, folder_ids, document_ids):
    # Fetch the product instance to link with folders and documents correctly
    product = Product.objects.get(id=product_id)
    
    # Grant access to specified folders (without recursive access to contents)
    for folder_id in folder_ids:
        folder = Folder.objects.get(id=folder_id, product=product)
        AccessPermission.objects.get_or_create(exporter=user, importer=partner, folder=folder, product=product)
    
    # Grant access to specified documents and their immediate parent folder only
    for document_id in document_ids:
        document = Document.objects.get(id=document_id)
        # Link the document to its folder and product correctly
        AccessPermission.objects.get_or_create(exporter=user, importer=partner, document=document, product=product)
        # If the document has a folder, grant access to this folder as well
        if document.folder:
            AccessPermission.objects.get_or_create(exporter=user, importer=partner, folder=document.folder, product=product)

def grant_access_to_folder(user, partner, folder, product_id):
    # Grant access to the current folder
    AccessPermission.objects.get_or_create(exporter=user, importer=partner, folder=folder, product_id=product_id)
    # Grant access to all documents in the current folder
    for document in folder.documents.all():
        AccessPermission.objects.get_or_create(exporter=user, importer=partner, document=document, product_id=product_id)
    # Recursively grant access to all subfolders and their documents
    for subfolder in folder.subfolders.all():
        grant_access_to_folder(user, partner, subfolder, product_id)

def grant_access_to_document(user, partner, document, product_id):
    # Directly use document.folder without additional query
    AccessPermission.objects.get_or_create(
        exporter=user,
        importer=partner,
        document=document,
        folder=document.folder,  # Use the document's related folder directly
        product_id=product_id
    )

@csrf_exempt
@require_POST
def remove_access(request, access_id):
    try:
        access_permission = AccessPermission.objects.get(id=access_id, exporter=request.user)
        access_permission.delete()
        return JsonResponse({'success': True, 'message': 'Access successfully removed.'})
    except AccessPermission.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Access permission not found or you do not have permission to remove it.'}, status=404)