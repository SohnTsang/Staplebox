# views.py
import json, os
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
from django.http import JsonResponse, Http404
from django.db.models import Q
from .utils import grant_product_access, grant_folder_or_document_access
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import Product, Folder, Document, AccessPermission
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework.renderers import TemplateHTMLRenderer
import logging
from rest_framework.decorators import api_view, permission_classes
from partners.models import Partnership
from companies.models import CompanyProfile
from django.core.signing import Signer, BadSignature
from users.utils import log_user_activity
from django.db.models import Prefetch
from django.http import JsonResponse

signer = Signer()

logger = logging.getLogger(__name__)


class ManageAccessView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'access_control/manage_access.html'

    def get(self, request, product_uuid):
        try:
            unsigned_product_uuid = signer.unsign(product_uuid)
        except BadSignature:
            return Response({'error': 'Invalid product UUID'}, status=400)

        company_profile = request.user.userprofile.company_profiles.first()
        product = get_object_or_404(Product, uuid=unsigned_product_uuid)
        
        if product.company != company_profile:
            return Response({'error': 'Unauthorized'}, status=403)

        partner_info = get_partner_info(company_profile)
        partners_with_access = get_partners_with_access(product)

        form = AccessPermissionForm(company_profile=company_profile, product_uuid=product.uuid)
        
        root_folders = Folder.objects.filter(product=product, parent__isnull=True).order_by('name')
        
        root_folders_data = []

        def collect_folders_data(folder, depth=1):
            subfolders_data = []
            subfolder_qs = Folder.objects.filter(parent=folder).order_by('name')
            for subfolder in subfolder_qs:
                subfolders_data.append({
                    'folder': subfolder,
                    'documents': [{'uuid': signer.sign(str(doc.uuid)), 'document': doc, 'depth': depth + 1} for doc in Document.objects.filter(folder=subfolder).order_by('original_filename')],
                    'folder_uuid': signer.sign(str(subfolder.uuid)),
                    'depth': depth + 1,  # Correct depth for subfolders
                    'subfolders': collect_folders_data(subfolder, depth + 1)  # Recursively collect subfolders with correct depth
                })
            return subfolders_data

        for root_folder in root_folders:
            # Directly add subfolders and documents of root folders at depth 1
            subfolder_qs = Folder.objects.filter(parent=root_folder).order_by('name')
            for subfolder in subfolder_qs:
                root_folders_data.append({
                    'folder': subfolder,
                    'documents': [{'uuid': signer.sign(str(doc.uuid)), 'document': doc, 'depth': 1} for doc in Document.objects.filter(folder=subfolder).order_by('original_filename')],
                    'folder_uuid': signer.sign(str(subfolder.uuid)),
                    'depth': 1,
                    'subfolders': collect_folders_data(subfolder, depth=1)
                })

            # Also, add documents directly under the root folder as depth 1
            root_folders_data.extend([
                {
                    'folder': None,  # No folder associated
                    'documents': [{'uuid': signer.sign(str(doc.uuid)), 'document': doc, 'depth': 1} for doc in Document.objects.filter(folder=root_folder).order_by('original_filename')],
                    'folder_uuid': signer.sign(str(root_folder.uuid)),  # This could be used to distinguish these documents
                    'depth': 1,
                    'subfolders': []
                }
            ])

        # Sign the product UUID again before passing to the template
        signed_product_uuid = signer.sign(str(product.uuid))

        context = {
            'product': product,
            'product_uuid': signed_product_uuid,  # Pass the signed product UUID
            'partners': partner_info,
            'documents': [],  # Excluding direct root documents as they are now part of root_folders_data
            'folders': [],  # Root folders are not needed in the context as they are unneeded at depth 1
            'root_folders_data': root_folders_data,
            'partners_with_access': partners_with_access,
            'form': form,
            'last_active_tab': request.session.get('last_active_tab', 'all'),
        }

        return Response(context)

    def post(self, request, product_uuid):
        try:
            unsigned_product_uuid = signer.unsign(product_uuid)
        except BadSignature:
            return Response({'error': 'Invalid product UUID'}, status=400)

        product = get_object_or_404(Product, uuid=unsigned_product_uuid)
        company_profile = request.user.userprofile.company_profiles.first()
        if product.company != company_profile:
            return Response({'error': 'Unauthorized'}, status=403)

        form = AccessPermissionForm(request.POST, company_profile=company_profile, product_uuid=product.uuid)
        if form.is_valid():
            action = request.POST.get('action')
            partners = form.cleaned_data['partners']
            folder_uuids = request.POST.getlist('folders')
            document_uuids = request.POST.getlist('documents')

            # Debugging: Log the data being processed
            logger.debug(f"Action: {action}")
            logger.debug(f"Partners: {partners}")
            logger.debug(f"Folder UUIDs: {folder_uuids}")
            logger.debug(f"Document UUIDs: {document_uuids}")

            with transaction.atomic():
                if action == 'grant_access':
                    self.grant_access(company_profile, partners, product, folder_uuids, document_uuids)
                elif action == 'update_access':
                    self.update_access(company_profile, partners, product, folder_uuids, document_uuids)

            messages.success(request, "Access updated successfully.")
            return redirect('access_control:manage_access', product_uuid=product_uuid)
        else:
            messages.error(request, "Invalid form submission.")
            return self.get(request, product_uuid)

    def grant_access(self, company_profile, partners, product, folder_uuids, document_uuids):
        logger.debug("Granting access...")
        for partner in partners:
            for folder_uuid in folder_uuids:
                try:
                    folder = get_object_or_404(Folder, uuid=folder_uuid)
                    logger.debug(f"Granting folder access to: {folder.uuid}")
                    AccessPermission.objects.get_or_create(partner1=company_profile, partner2=partner, product=product, folder=folder)
                except Exception as e:
                    logger.error(f"Error granting folder access: {e}")
            
            for document_uuid in document_uuids:
                try:
                    document = get_object_or_404(Document, uuid=document_uuid)
                    logger.debug(f"Granting document access to: {document.uuid}")
                    AccessPermission.objects.get_or_create(partner1=company_profile, partner2=partner, product=product, document=document)
                except Exception as e:
                    logger.error(f"Error granting document access: {e}")
        logger.debug("Completed grant_access method.")

    def update_access(self, company_profile, partners, product, folder_uuids, document_uuids):
        logger.debug("Starting update_access method...")

        for partner in partners:
            partner_profile = get_object_or_404(CompanyProfile, uuid=partner.uuid)
            
            # Deleting existing permissions before re-granting
            existing_permissions = AccessPermission.objects.filter(partner1=company_profile, partner2=partner_profile, product=product)
            permissions_count = existing_permissions.count()
            existing_permissions.delete()
            logger.info(f"Deleted {permissions_count} existing permissions for company profile {company_profile.name} and partner {partner_profile.name}")
            
            # Re-grant access with possibly updated folders and documents
            self.grant_access(company_profile, [partner_profile], product, folder_uuids, document_uuids)

        logger.debug("Completed update_access method.")




@api_view(['POST'])
@permission_classes([IsAuthenticated])
def access_control_modal(request, product_uuid):
    try:
        unsigned_product_uuid = signer.unsign(product_uuid)
    except BadSignature:
        raise Http404("Invalid product UUID")

    print(request.data)  # Debugging line to print the entire incoming data

    item_ids = request.data.get('item_id').split(',')
    item_types = request.data.get('item_type').split(',')
    signed_partner_ids = request.data.getlist('partners')

    if len(item_ids) != len(item_types):
        return Response({'error': 'Mismatched item_ids and item_types'}, status=status.HTTP_400_BAD_REQUEST)

    logger.debug(f'Received data: item_ids={item_ids}, item_types={item_types}, signed_partner_ids={signed_partner_ids}')

    user_company_profile = request.user.userprofile.company_profiles.first()
    product = get_object_or_404(Product, uuid=unsigned_product_uuid)

    # Unsign the partner IDs and fetch the CompanyProfile instances
    try:
        partner_ids = [signer.unsign(partner_id) for partner_id in signed_partner_ids]
    except BadSignature:
        return Response({'error': 'Invalid partner ID'}, status=status.HTTP_400_BAD_REQUEST)

    selected_partners = CompanyProfile.objects.filter(uuid__in=partner_ids)

    for item_id, item_type in zip(item_ids, item_types):
        try:
            unsigned_item_id = signer.unsign(item_id)
        except BadSignature:
            raise Http404("Invalid item UUID")

        if item_type == 'folder':
            item = get_object_or_404(Folder, uuid=unsigned_item_id)
            for partner in selected_partners:
                grant_folder_or_document_access(user_company_profile, partner, product, folder=item)

                log_user_activity(
                    user=request.user,
                    action=f"Granted access to folder '{item.name}' for partner '{partner.name}'",
                    activity_type="ACCESS_PERMISSION_GRANTED",
                    item_name= "Product: " + product.product_name
                )
        elif item_type == 'document':
            item = get_object_or_404(Document, uuid=unsigned_item_id)
            for partner in selected_partners:
                grant_folder_or_document_access(user_company_profile, partner, product, document=item)

                log_user_activity(
                    user=request.user,
                    action=f"Granted access to document '{item.display_filename}' for partner '{partner.name}'",
                    activity_type="ACCESS_PERMISSION_GRANTED",
                    item_name= "Product: " + product.product_name
                )

        else:
            return Response({'error': 'Invalid item type'}, status=status.HTTP_400_BAD_REQUEST)

    success_message = 'Access granted'
    if len(partner_ids) > 1:
        success_message = 'Access granted to all selected partners'
    return Response({'success': success_message}, status=status.HTTP_200_OK)


@login_required
def get_all_partners(request):
    user = request.user

    query = Q(partner1=user) | Q(partner2=user)
    query &= Q(is_active=True)
    partnerships = Partnership.objects.filter(query).distinct()

    partners_data = []
    for partnership in partnerships:
        partner = partnership.partner2 if partnership.partner1 == user else partnership.partner1
        try:
            profile = CompanyProfile.objects.get(user_profiles=partner.userprofile)
            partners_data.append({
                'partner_id': signer.sign(str(partner.id)),
                'company_name': profile.name,
                'company_role': profile.role.capitalize() if profile.role else None,
            })
        except CompanyProfile.DoesNotExist:
            continue

    return JsonResponse(partners_data, safe=False)


@login_required
def get_partners_without_access(request, product_uuid, item_uuid, item_type):
    try:
        unsigned_product_uuid = signer.unsign(product_uuid)
        unsigned_item_uuid = signer.unsign(item_uuid)
    except BadSignature:
        raise Http404("Invalid UUID")

    user = request.user
    product = get_object_or_404(Product, uuid=unsigned_product_uuid)

    if item_type == 'folder':
        item = get_object_or_404(Folder, uuid=unsigned_item_uuid)
        granted_partners = AccessPermission.objects.filter(folder=item).values_list('partner2', flat=True)
    elif item_type == 'document':
        item = get_object_or_404(Document, uuid=unsigned_item_uuid)
        granted_partners = AccessPermission.objects.filter(document=item).values_list('partner2', flat=True)
    else:
        return JsonResponse({'error': 'Invalid item type'}, status=400)

    # Get the user's company profiles
    user_company_profiles = CompanyProfile.objects.filter(user_profiles__user=user)

    if not user_company_profiles.exists():
        return JsonResponse([], safe=False)

    # Construct the query to filter partnerships where the user's company profile is either partner1 or partner2
    query = Q(partner1__in=user_company_profiles) | Q(partner2__in=user_company_profiles)
    query &= Q(is_active=True)
    partnerships = Partnership.objects.filter(query).distinct()

    partners_data = []
    for partnership in partnerships:
        partner = partnership.partner2 if partnership.partner1 in user_company_profiles else partnership.partner1
        if partner.uuid not in granted_partners:
            partners_data.append({
                'partner_id': signer.sign(str(partner.uuid)),
                'company_name': partner.name,
                'company_role': partner.role.capitalize() if partner.role else None,
            })

    return JsonResponse(partners_data, safe=False)

@login_required
def get_partners_with_access_json(request, item_uuid=None, item_type=None):
    if item_type not in ['document', 'folder']:
        return JsonResponse({'error': 'Invalid item type'}, status=400)

    try:
        unsigned_item_uuid = signer.unsign(item_uuid)
    except BadSignature:
        raise Http404("Invalid item UUID")

    item_model = Document if item_type == "document" else Folder
    item = get_object_or_404(item_model, uuid=unsigned_item_uuid)

    if item_type == "folder":
        product_condition = Q(product=item.product)
    elif item_type == "document":
        product_condition = Q(product=item.folder.product)

    # Get the user's company profile
    user_company_profiles = request.user.userprofile.company_profiles.all()

    permissions = AccessPermission.objects.filter(
        Q(**{item_type: item}) | product_condition & Q(folder__isnull=True, document__isnull=True)
    ).distinct().select_related('partner2', 'partner1')  # Include partner1 in the query

    partners_data = []
    for permission in permissions:
        if permission.partner1 in user_company_profiles:
            real_partner = permission.partner2
        else:
            real_partner = permission.partner1

        partners_data.append({
            'partner_id': signer.sign(str(real_partner.uuid)),
            'company_name': real_partner.name,
            'company_role': real_partner.role.capitalize() if real_partner.role else 'N/A',
            'access_detail': 'Full Access'
        })

    return JsonResponse(partners_data, safe=False)


@login_required
def fetch_partner_access_details(request, product_uuid, partner_uuid):
    signer = Signer()

    try:
        unsigned_product_uuid = signer.unsign(product_uuid)
        unsigned_partner_uuid = signer.unsign(partner_uuid)
    except BadSignature as e:
        logger.error(f"BadSignature Error: {str(e)} - product_uuid: {product_uuid}, partner_uuid: {partner_uuid}")
        return JsonResponse({'error': 'Invalid UUID'}, status=400)

    logger.debug(f"Unsigned Product UUID: {unsigned_product_uuid}")
    logger.debug(f"Unsigned Partner UUID: {unsigned_partner_uuid}")

    # Ensure the user requesting this page is the product owner or has permission to view this information
    company_profile = request.user.userprofile.company_profiles.first()
    product = get_object_or_404(Product, uuid=unsigned_product_uuid)
    partner = get_object_or_404(CompanyProfile, uuid=unsigned_partner_uuid)

    logger.debug(f"Company Profile: {company_profile}")
    logger.debug(f"Product: {product}")
    logger.debug(f"Partner: {partner}")

    if product.company != company_profile:
        logger.warning(f"Unauthorized Access Attempt: {company_profile} attempted to access {product}")
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    # Determine if the user is partner1 or partner2
    partnership = get_object_or_404(Partnership, 
                                    Q(partner1=company_profile, partner2=partner) | 
                                    Q(partner1=partner, partner2=company_profile))

    if partnership.partner1 == company_profile:
        is_partner1 = True
    else:
        is_partner1 = False

    logger.debug(f"Is Partner1: {is_partner1}")

    if is_partner1:
        product_access = AccessPermission.objects.filter(
            partner2=partner, product=product, folder__isnull=True, document__isnull=True
        ).exists()

        folders_access = AccessPermission.objects.filter(
            partner2=partner, product=product, folder__isnull=False
        ).values_list('folder__uuid', flat=True)

        documents_access = AccessPermission.objects.filter(
            partner2=partner, product=product, document__isnull=False
        ).values_list('document__uuid', flat=True)
    else:
        product_access = AccessPermission.objects.filter(
            partner1=partner, product=product, folder__isnull=True, document__isnull=True
        ).exists()

        folders_access = AccessPermission.objects.filter(
            partner1=partner, product=product, folder__isnull=False
        ).values_list('folder__uuid', flat=True)

        documents_access = AccessPermission.objects.filter(
            partner1=partner, product=product, document__isnull=False
        ).values_list('document__uuid', flat=True)

    logger.debug(f"Product Access: {product_access}")
    logger.debug(f"Folders Access List: {folders_access}")
    logger.debug(f"Documents Access List: {documents_access}")

    # Convert querysets to lists (as querysets are not JSON serializable directly)
    folders_access_list = [signer.sign(str(uuid)) for uuid in folders_access]
    documents_access_list = [signer.sign(str(uuid)) for uuid in documents_access]

    logger.debug(f"Signed Folders Access List: {folders_access_list}")
    logger.debug(f"Signed Documents Access List: {documents_access_list}")

    # Return the access details as a JSON response
    return JsonResponse({
        'folders': folders_access_list,
        'documents': documents_access_list,
        'product_access': product_access,
    })




@login_required
@require_POST
def remove_access(request, product_id, partner_id):
    request.session['last_active_tab'] = 'current'
    if request.user.is_authenticated:
        product = get_object_or_404(Product, pk=product_id)
        if product.user != request.user:
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
        
        partner = get_object_or_404(CompanyProfile, pk=partner_id)

        AccessPermission.objects.filter(product=product, partner2_id=partner_id).delete()
        
        log_user_activity(
            user=request.user,
            action=f"Removed access for partner '{partner.name}'",
            activity_type="ACCESS_PERMISSION_REVOKED",
            item_name= "Product: " + product.product_name
        )

        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=404)


@login_required
@require_POST
def remove_specific_access(request, product_uuid, entity_type, entity_uuid):
    try:
        # Unsign the product UUID and entity UUID
        unsigned_product_uuid = signer.unsign(product_uuid)
        unsigned_entity_uuid = signer.unsign(entity_uuid)
    except BadSignature:
        return JsonResponse({'success': False, 'error': 'Invalid UUID'}, status=400)

    # Get the product and check user authorization
    product = get_object_or_404(Product, uuid=unsigned_product_uuid)
    if product.user != request.user:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

    # Parse the partner UUID from the request body and unsign it
    try:
        data = json.loads(request.body)
        partner_id = data.get('partner_id')
        if not partner_id:
            raise ValueError("Partner ID is required")

        unsigned_partner_id = signer.unsign(partner_id)
        partner = get_object_or_404(CompanyProfile, uuid=unsigned_partner_id)
    except (json.JSONDecodeError, BadSignature, ValueError) as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

    # Determine the model based on the entity type and get the entity
    entity_model = Document if entity_type == "document" else Folder
    entity = get_object_or_404(entity_model, uuid=unsigned_entity_uuid)

    # Remove the access permission for the entity and all sub-entities
    def remove_access_recursively(folder):
        # Remove access for the folder itself
        AccessPermission.objects.filter(
            product=product, partner2_id=unsigned_partner_id, folder=folder
        ).delete()

        # Remove access for all documents in this folder
        AccessPermission.objects.filter(
            product=product, partner2_id=unsigned_partner_id, document__folder=folder
        ).delete()

        # Recursively remove access for all subfolders and their contents
        for subfolder in folder.subfolders.all():
            remove_access_recursively(subfolder)

    if entity_type == "folder":
        remove_access_recursively(entity)
        # Log the activity
        log_user_activity(
            user=request.user,
            action=f"Removed access to folder '{entity.name}' for partner '{partner.name}'",
            activity_type="ACCESS_PERMISSION_REVOKED",
            item_name=f"Product: {product.product_name}"
        )
    elif entity_type == "document":
        AccessPermission.objects.filter(
            product=product, partner2_id=unsigned_partner_id, document=entity
        ).delete()
        # Log the activity
        log_user_activity(
            user=request.user,
            action=f"Removed access to document '{entity.display_filename}' for partner '{partner.name}'",
            activity_type="ACCESS_PERMISSION_REVOKED",
            item_name=f"Product: {product.product_name}"
        )
    else:
        return JsonResponse({'success': False, 'error': 'Invalid entity type'}, status=400)

    return JsonResponse({'success': True})




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
                update_access(request, product.uuid)
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


