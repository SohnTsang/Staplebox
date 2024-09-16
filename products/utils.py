from django.shortcuts import redirect
from django.core.signing import Signer
from django.http import HttpResponseForbidden
import logging
from django.db.models import Q
from access_control.models import AccessPermission

signer = Signer()

logger = logging.getLogger(__name__)


def get_breadcrumbs(folder, product):
    # Initialize with the root breadcrumb
    breadcrumbs = [{'id': product.uuid, 'name': product.product_name, 'is_root': True}]
    if folder.is_root:
        return breadcrumbs

    # Get ancestors including the current folder
    ancestors = folder.get_ancestors(include_self=True)
    for ancestor in ancestors:
        if ancestor.is_root:
            continue  # Skip root since it's already added
        breadcrumbs.append({'id': ancestor.id, 'name': ancestor.name, 'is_root': False})

    return breadcrumbs


def redirect_to_correct_view(request, product, current_view):
    """
    Redirect to the correct view based on whether the user is the owner or a partner with access.
    """
    company_profile = request.user.userprofile.company_profiles.first()
    
    # Get the owner company profile of the product
    owner_company_profile = product.company

    # If the user's company profile is the same as the owner's company profile, they access the ProductExplorerView
    if owner_company_profile == company_profile:
        if current_view == 'ProductExplorerView':
            return None  # No redirect needed, the user is already on the correct view
        return redirect('products:product_explorer', product_uuid=signer.sign(str(product.uuid)))

    # Otherwise, check if the user has access as a partner
    partner_permissions = AccessPermission.objects.filter(
        (Q(partner1=company_profile) | Q(partner2=company_profile)) & 
        Q(product=product)
    )

    if partner_permissions.exists():
        # If the user is a partner with access, ensure they are on the PartnerProductExplorerView
        if current_view == 'PartnerProductExplorerView':
            return None  # No redirect needed, the user is already on the correct view
        return redirect('products:partner_product_explorer', product_uuid=signer.sign(str(product.uuid)), partner_uuid=signer.sign(str(company_profile.uuid)))

    # If neither owner nor partner, raise a 403 Forbidden error
    return HttpResponseForbidden("You do not have permission to access this product.")