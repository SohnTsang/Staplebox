# views.py
import json, os
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render
from .models import Product, Folder, Document, AccessPermission
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Prefetch
from .forms import AccessPermissionForm
from django.db import transaction
from partners.utils import get_partner_info
from access_control.utils import get_partners_with_access
from django.http import JsonResponse
from django.db.models import Q
from users.models import UserProfile
from .utils import grant_product_access, grant_folder_or_document_access
from django.http import HttpResponseNotAllowed
from django.views.decorators.http import require_http_methods
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import Product, Folder, Document, AccessPermission
from .serializers import AccessPermissionSerializer
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework.renderers import TemplateHTMLRenderer
import logging
from rest_framework.decorators import api_view, permission_classes

logger = logging.getLogger(__name__)


class ManageAccessView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'access_control/manage_access.html'

    def get(self, request, product_id):
        user = request.user
        product = get_object_or_404(Product, id=product_id)
        
        if product.user != user:
            return Response({'error': 'Unauthorized'}, status=403)

        partner_info = get_partner_info(user)
        partners_with_access = get_partners_with_access(product)
        
        form = AccessPermissionForm(user=user, product_id=product_id)
        
        root_folders = Folder.objects.filter(product=product, parent__isnull=True)
        documents = Document.objects.filter(folder__in=root_folders)

        folders_data = []
        for root_folder in root_folders:
            subfolders = Folder.objects.filter(parent=root_folder)
            for subfolder in subfolders:
                subfolder_documents = Document.objects.filter(folder=subfolder)
                folders_data.append({'folder': subfolder, 'documents': subfolder_documents})

        for root_folder in root_folders:
            root_folder_documents = Document.objects.filter(folder=root_folder)
            if root_folder_documents.exists():
                folders_data.append({'folder': None, 'documents': root_folder_documents})

        context = {
            'product': product,
            'partners': partner_info,
            'documents': documents,
            'folders': root_folders,
            'folders_data': folders_data,
            'partners_with_access': partners_with_access,
            'form': form,
            'last_active_tab': request.session.get('last_active_tab', 'all'),
        }
        return Response(context)

    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        if product.user != request.user:
            return Response({'error': 'Unauthorized'}, status=403)

        form = AccessPermissionForm(request.POST, user=request.user, product_id=product_id)
        if form.is_valid():
            action = request.POST.get('action')
            partners = form.cleaned_data['partners']
            folder_ids = request.POST.getlist('folders')
            document_ids = request.POST.getlist('documents')

            with transaction.atomic():
                if action == 'grant_access':
                    self.grant_access(request.user, partners, product, folder_ids, document_ids)
                elif action == 'update_access':
                    self.update_access(request.user, partners, product, folder_ids, document_ids)

            messages.success(request, "Access updated successfully.")
            return redirect('access_control:manage_access', product_id=product_id)
        else:
            messages.error(request, "Invalid form submission.")
            return self.get(request, product_id)

    def grant_access(self, user, partners, product, folder_ids, document_ids):
        logger.debug("Granting access...")
        for partner in partners:
            logger.debug(f"Partner ID: {partner.id}")  # Ensure this is the expected numeric ID
            for folder_id in folder_ids:
                logger.debug(f"Folder ID: {folder_id}")  # Log to confirm correct data type
                folder = get_object_or_404(Folder, id=folder_id)
                AccessPermission.objects.get_or_create(partner1=user, partner2=partner, product=product, folder=folder)
            for document_id in document_ids:
                logger.debug(f"Document ID: {document_id}")  # Log to confirm correct data type
                document = get_object_or_404(Document, id=document_id)
                AccessPermission.objects.get_or_create(partner1=user, partner2=partner, product=product, document=document)
        logger.debug("Completed grant_access method.")

    def update_access(self, user, partners, product, folder_ids, document_ids):
        logger.debug("Starting update_access method...")
        
        # Assuming partners are now coming as user instances or IDs, handle both cases
        for partner in partners:
            partner_id = partner if isinstance(partner, int) else partner.id
            logger.debug(f"Processing partner ID: {partner_id}")
            
            try:
                partner_user = get_object_or_404(User, id=partner_id)
                logger.debug(f"Found User: {partner_user.username} with ID: {partner_id}")
            except Exception as e:
                logger.error(f"Error finding user with ID {partner_id}: {str(e)}")
                continue
            
            # Deleting existing permissions before re-granting
            existing_permissions = AccessPermission.objects.filter(partner1=user, partner2=partner_user, product=product)
            permissions_count = existing_permissions.count()
            existing_permissions.delete()
            logger.info(f"Deleted {permissions_count} existing permissions for user {user.username} and partner {partner_user.username}")
            
            # Re-grant access with possibly updated folders and documents
            self.grant_access(user, [partner_user], product, folder_ids, document_ids)

        logger.debug("Completed update_access method.")


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def access_control_modal(request, product_id):
    item_id = request.data.get('item_id')
    item_type = request.data.get('item_type')
    partner_ids = request.data.getlist('partners')
    user = request.user
    product = get_object_or_404(Product, id=product_id)

    selected_partners = User.objects.filter(id__in=partner_ids)
    
    if item_type == 'folder':
        item = get_object_or_404(Folder, id=item_id)
        for partner in selected_partners:
            grant_folder_or_document_access(user, partner, product, folder=item)
    elif item_type == 'document':
        item = get_object_or_404(Document, id=item_id)
        for partner in selected_partners:
            grant_folder_or_document_access(user, partner, product, document=item)
    else:
        return Response({'error': 'Invalid item type'}, status=status.HTTP_400_BAD_REQUEST)

    return Response({'success': 'Access granted'}, status=status.HTTP_200_OK)


@login_required
@require_http_methods(["POST"])
def access_control_modal_original(request, product_id):
    print("Access control view reached.")
    print("POST data:", request.POST)
    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        item_type = request.POST.get('item_type')
        partner_ids = request.POST.getlist('partners')  # Assuming checkboxes have names set to 'partners'
        user = request.user
        product = get_object_or_404(Product, id=product_id)

        # Retrieve selected partners based on IDs
        selected_partners = User.objects.filter(id__in=partner_ids)
        
        # Based on item_type, find the corresponding folder or document
        if item_type == 'folder':
            item = get_object_or_404(Folder, id=item_id)
            for partner in selected_partners:
                grant_folder_or_document_access(user, partner, product, folder=item)
        elif item_type == 'document':
            item = get_object_or_404(Document, id=item_id)
            for partner in selected_partners:
                grant_folder_or_document_access(user, partner, product, document=item)
        else:
            return HttpResponseNotAllowed("Invalid item type")

        return redirect('products:product_explorer', product_id=product_id)
    else:
        # Handle non-POST requests if necessary
        return HttpResponseNotAllowed("This URL only accepts POST requests")
    

@login_required
def fetch_partner_access_details(request, product_id, partner_id):
    # Ensure the user requesting this page is the product owner or has permission to view this information
    product = get_object_or_404(Product, id=product_id)
    partner = User.objects.get(id=partner_id)

    if product.user != request.user:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    product_access = AccessPermission.objects.filter(partner2=partner, product=product, folder__isnull=True, document__isnull=True).exists()
    # Fetch access details for the given partner and product
    folders_access = AccessPermission.objects.filter(partner2_id=partner_id, product_id=product_id, folder__isnull=False).values_list('folder_id', flat=True)
    documents_access = AccessPermission.objects.filter(partner2_id=partner_id, product_id=product_id, document__isnull=False).values_list('document_id', flat=True)

    # Convert querysets to lists (as querysets are not JSON serializable directly)
    folders_access_list = list(folders_access)
    documents_access_list = list(documents_access)

    # Return the access details as a JSON response
    return JsonResponse({
        'folders': folders_access_list,
        'documents': documents_access_list,
        'product_access': product_access,
    })



@login_required
def get_partners_with_access_json(request, item_id=None, item_type=None):
    if item_type not in ['document', 'folder']:
        return JsonResponse({'error': 'Invalid item type'}, status=400)
    
    item_model = Document if item_type == "document" else Folder
    item = get_object_or_404(item_model, pk=item_id)

    if item_type == "folder":
        item = get_object_or_404(Folder, pk=item_id)
        product_condition = Q(product=item.product)
    elif item_type == "document":
        item = get_object_or_404(Document, pk=item_id)
        product_condition = Q(product=item.folder.product)  # Assuming Document is related to Folder which in turn is related to Product

    # Filter for specific item or product-level permissions
    permissions = AccessPermission.objects.filter(
        Q(**{item_type: item}) | product_condition & Q(folder__isnull=True, document__isnull=True)
    ).distinct().select_related('partner2').prefetch_related(
        Prefetch('partner2__userprofile', queryset=UserProfile.objects.select_related('companyprofile'))
    )

    partners_data = []
    for permission in permissions:
        user_profile = getattr(permission.partner2, 'userprofile', None)
        company_profile = getattr(user_profile, 'companyprofile', None) if user_profile else None
        partners_data.append({
            'partner2_id': permission.partner2.id,
            'company_name': getattr(company_profile, 'name', 'N/A'),
            'company_role': getattr(company_profile, 'role', 'N/A').capitalize(),
            'access_detail': 'Full Access'
        })

    return JsonResponse(partners_data, safe=False)


@login_required
@require_POST
def remove_access(request, product_id, partner_id):
    request.session['last_active_tab'] = 'current'
    if request.user.is_authenticated:
        product = get_object_or_404(Product, pk=product_id)
        if product.user != request.user:
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
        
        AccessPermission.objects.filter(product=product, partner2_id=partner_id).delete()
        
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=404)


@login_required
@require_POST
def remove_specific_access(request, product_id, entity_type, entity_id):
    product = get_object_or_404(Product, pk=product_id)
    if product.user != request.user:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

    entity_model = None
    if entity_type == 'folder':
        entity_model = get_object_or_404(Folder, pk=entity_id)
    elif entity_type == 'document':
        entity_model = get_object_or_404(Document, pk=entity_id)
    
    if entity_model and AccessPermission.objects.filter(product=product, partner2_id=request.POST.get('partner_id'), **{entity_type: entity_model}).exists():
        AccessPermission.objects.filter(product=product, partner2_id=request.POST.get('partner_id'), **{entity_type: entity_model}).delete()
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'error': 'Not Found'}, status=403)


@login_required
@require_POST
def remove_specific_access(request, product_id, entity_type, entity_id):
    # Check if the product exists and the user has rights
    product = get_object_or_404(Product, pk=product_id)
    if product.user != request.user:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    # Determine the entity model based on the type
    entity_model = None
    if entity_type == 'folder':
        entity_model = get_object_or_404(Folder, pk=entity_id)
    elif entity_type == 'document':
        entity_model = get_object_or_404(Document, pk=entity_id)
    
    # Get partner_id from POST data
    partner_id = request.POST.get('partner_id')
    if not partner_id:
        return JsonResponse({'success': False, 'error': 'Partner ID is required'}, status=400)

    # Perform the deletion if the permission exists
    if entity_model:
        permission_qs = AccessPermission.objects.filter(
            product=product,
            partner2_id=partner_id,
            **{entity_type: entity_model}
        )
        if permission_qs.exists():
            permission_qs.delete()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'No such permission'}, status=404)
    
    return JsonResponse({'success': False, 'error': 'Invalid entity type'}, status=400)


################################################################################################################################################


@login_required
def manage_access(request, product_id):
    user = request.user
    partner_info = get_partner_info(user)
    product = get_object_or_404(Product, id=product_id)
    
    partners_with_access = get_partners_with_access(product)
    
    # Ensure the user requesting this page is the product owner
    if product.user != user:
        messages.error(request, "You are not authorized to manage access for this product.")
        return redirect('home')  # Update with your actual redirect

    form = AccessPermissionForm(request.POST or None, user=user, product_id=product_id)
    # Processing form submission (grant access)
    if request.method == 'POST' and form.is_valid():
        action = request.POST.get('action')
        partners = form.cleaned_data['partners']  # This should be a queryset of User instances.
        folder_ids = request.POST.getlist('folders')
        document_ids = request.POST.getlist('documents')

        with transaction.atomic():
            if action == 'update_access':
                request.session['last_active_tab'] = 'current'
                update_access(request, product.id)
            elif action == 'grant_access':
                # Extracting selected partner IDs, folder IDs, and document IDs from form.cleaned_data
                request.session['last_active_tab'] = 'all'
                total_folders = Folder.objects.filter(product=product).exclude(name='Root').values_list('id', flat=True)
                total_documents = Document.objects.filter(folder__product=product).values_list('id', flat=True)

                total_folder_ids = set(map(str, total_folders))
                total_document_ids = set(map(str, total_documents))


                all_folders_selected = total_folder_ids <= set(folder_ids)
                all_documents_selected = total_document_ids <= set(document_ids)

                granting_product_level_access = all_folders_selected and all_documents_selected

                granted_new_access = False
                redundant_access = False

                is_product_empty = not total_folders and not total_documents

                for partner in partners:
                    if granting_product_level_access:
                        if not is_product_empty:
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
                    messages.success(request, "Access granted.")
                elif redundant_access:
                    messages.info(request, "Existing access was sufficient.")
                else:
                    messages.warning(request, "Please select partners and items for granting access")

            else:
                request.session['last_active_tab'] = 'all'

                # Redirect to avoid re-posting form data
            return redirect('access_control:manage_access', product_id=product_id)
            
    else:
        
        form = AccessPermissionForm(user=request.user, product_id=product_id)
        
    # Fetching active partnerships, folders, and documents as before for display
    root_folders = Folder.objects.filter(product=product, parent__isnull=True)
    documents = Document.objects.filter(folder__in=root_folders)

    folders_data = []
    for root_folder in root_folders:
        subfolders = Folder.objects.filter(parent=root_folder)  # Direct children of each root folder
        for subfolder in subfolders:
            documents = Document.objects.filter(folder=subfolder)
            folders_data.append({'folder': subfolder, 'documents': documents})
            # If you also need to fetch subfolders of subfolders recursively, you'll need a more complex approach

    # If root_folders should also include documents directly under them without a subfolder
    for root_folder in root_folders:
        documents = Document.objects.filter(folder=root_folder)
        if documents.exists():
            folders_data.append({'folder': None, 'documents': documents})
    


    context = {
        'product': product,
        'partners': partner_info,
        'documents': documents,
        'folders': root_folders,
        'folders_data': folders_data,
        'partners_with_access': partners_with_access,
        'form': form,  # Include the form in the context
        'last_active_tab': request.session.get('last_active_tab', 'all'),
    }

    return render(request, 'access_control/manage_access.html', context)


