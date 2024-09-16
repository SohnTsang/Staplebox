from django.db.models import Count
from .models import Product, Folder, Document, AccessPermission
from companies.models import CompanyProfile
from django.db.models import Q
from rest_framework.response import Response
from rest_framework import status
from django.core.signing import Signer
import logging

logger = logging.getLogger(__name__)

signer = Signer()

class AccessControlMixin:
    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object_to_check(request, *args, **kwargs)
        if not obj or not self.has_access(request.user.userprofile.company_profiles.first(), obj):
            return self.handle_permission_denied(request)
        return super().dispatch(request, *args, **kwargs)

    def get_object_to_check(self, request, *args, **kwargs):
        raise NotImplementedError("Must override get_object_to_check method")

    def has_access(self, company_profile, obj):
        # By default, check using company_has_access_to
        return company_has_access_to(company_profile, obj)

    def handle_permission_denied(self, request):
        response = Response({'error': 'You do not have access to this function'}, status=status.HTTP_403_FORBIDDEN)
        self._set_renderer_and_accept_language(request, response)
        return response

    def _set_renderer_and_accept_language(self, request, response):
        renderer = self.get_renderer(request)
        response.accepted_renderer = renderer
        response.accepted_media_type = renderer.media_type
        response.renderer_context = {
            'view': self,
            'args': self.args,
            'kwargs': self.kwargs,
            'request': request,
        }

    def get_renderer(self, request):
        return request.accepted_renderer if hasattr(request, 'accepted_renderer') else self.get_renderers()[0]
    

def get_partners_with_access(product):
    # Get the current user's company profile
    current_company_profile = product.company

    # Fetch permissions related to the product and prefetch necessary relationships
    permissions = AccessPermission.objects.filter(product=product).select_related('partner2').prefetch_related('folder', 'document')

    # Annotate the number of folders and documents each partner has access to
    permissions = permissions.values('partner2').annotate(
        folder_count=Count('folder', distinct=True),
        document_count=Count('document', distinct=True)
    )

    partners_with_access = []
    total_folders = Folder.objects.filter(product=product).exclude(name='Root').count()
    total_documents = Document.objects.filter(folder__product=product).count()

    for permission in permissions:
        partner = CompanyProfile.objects.get(uuid=permission['partner2'])

        # Skip the current user's company profile
        if partner == current_company_profile:
            continue

        product_access = AccessPermission.objects.filter(
            partner2=partner,
            product=product,
            folder__isnull=True,
            document__isnull=True
        ).exists()

        access_detail = f"{permission['folder_count']} folders and {permission['document_count']} documents"
        if product_access or (permission['folder_count'] == total_folders and permission['document_count'] == total_documents):
            access_detail = "All folders and documents"

        signed_partner_uuid = signer.sign(str(partner.uuid))

        partners_with_access.append({
            'access_detail': access_detail,
            'company_name': partner.name,
            'company_email': partner.email,
            'company_role': partner.role,
            'partner_uuid': signed_partner_uuid,  # Use the signed partner UUID here
        })

    return partners_with_access




def check_and_grant_access(user_company_profile, partner, product, folder=None, document=None, access_type='read_only'):
    model = Folder if folder else Document
    target = folder if folder else document

    higher_level_access_exists = AccessPermission.objects.filter(
        Q(partner2=partner) | Q(partner1=partner),
        product=product,
        folder__isnull=True,
        document__isnull=True,
        access_type=access_type
    ).exists()

    if higher_level_access_exists:
        return False

    filter_args = {'partner1': user_company_profile, 'partner2': partner, 'product': product, 'access_type': access_type}
    if folder:
        filter_args['folder'] = folder
    elif document:
        filter_args['document'] = document
    else:
        filter_args['folder__isnull'] = True
        filter_args['document__isnull'] = True

    permission, created = AccessPermission.objects.get_or_create(
        defaults=filter_args,
        **filter_args
    )

    if not created:
        if permission.access_type != access_type:
            permission.access_type = access_type
            permission.save()

    return created or permission.access_type != access_type


def grant_product_access(user_company_profile, partner, product):
    existing_permission = AccessPermission.objects.filter(
        Q(partner2=partner) | Q(partner1=partner),
        product=product,
        folder__isnull=True,
        document__isnull=True
    ).first()

    if existing_permission:
        AccessPermission.objects.filter(
            Q(partner2=partner) | Q(partner1=partner),
            product=product,
        ).exclude(
            id=existing_permission.id
        ).delete()
        return False
    else:
        permission, created = AccessPermission.objects.get_or_create(
            Q(partner2=partner) | Q(partner1=partner),
            product=product,
            defaults={'folder': None, 'document': None}
        )
        if created:
            AccessPermission.objects.filter(
                Q(partner2=partner) | Q(partner1=partner),
                product=product,
            ).exclude(
                id=permission.id
            ).delete()
        return created


def grant_folder_or_document_access(user_company_profile, partner, product, folder=None, document=None):
    # Check if access to the product itself exists
    product_access_exists = AccessPermission.objects.filter(
        partner2=partner,
        product=product,
        folder__isnull=True,
        document__isnull=True
    ).exists()

    # If access to the product exists, skip further processing
    if product_access_exists:
        return False

    # Ensure the root folder has access before granting any other access
    root_folder = Folder.objects.filter(product=product, is_root=True).first()
    if root_folder:
        root_access_exists = AccessPermission.objects.filter(
            partner2=partner,
            product=product,
            folder=root_folder
        ).exists()

        # If no access to the root folder, grant it
        if not root_access_exists:
            AccessPermission.objects.create(
                product=product,
                folder=root_folder,
                partner2=partner,
                partner1=user_company_profile,
                is_direct=False  # Inherited access
            )
            logger.debug(f"Granted access to root folder: {root_folder} for partner: {partner}")

    # Recursively grant access to all parent folders up to the root folder
    def grant_parent_access(current_folder):
        if not current_folder:
            return

        # Grant access to the current folder if not already granted
        parent_access_exists = AccessPermission.objects.filter(
            partner2=partner,
            product=product,
            folder=current_folder
        ).exists()

        if not parent_access_exists:
            AccessPermission.objects.create(
                product=product,
                folder=current_folder,
                partner2=partner,
                partner1=user_company_profile,
                is_direct=False  # Inherited access
            )
            logger.debug(f"Granted access to parent folder: {current_folder} for partner: {partner}")

        # Recursively check the parent folder
        if current_folder.parent:
            grant_parent_access(current_folder.parent)

    # If a folder is provided, grant access recursively up the folder structure
    if folder:
        # Grant access to the parent folders
        grant_parent_access(folder.parent)

        # Grant direct access to the specified folder
        AccessPermission.objects.get_or_create(
            product=product,
            folder=folder,
            partner2=partner,
            defaults={'partner1': user_company_profile, 'is_direct': True}
        )

        # Optionally grant access to subfolders and documents
        # If you don't want to grant access to subfolders and documents, comment out the following lines
        def grant_recursive_access(current_folder):
            for doc in current_folder.documents.all():
                AccessPermission.objects.get_or_create(
                    product=product,
                    document=doc,
                    partner2=partner,
                    defaults={'partner1': user_company_profile, 'is_direct': True}
                )
            # For subfolders, decide whether to grant access
            # If you don't want to grant access to subfolders, comment out the recursive call
            for subfolder in current_folder.subfolders.all():
                AccessPermission.objects.get_or_create(
                    product=product,
                    folder=subfolder,
                    partner2=partner,
                    defaults={'partner1': user_company_profile, 'is_direct': True}
                )
                grant_recursive_access(subfolder)  # Comment this out if not granting subfolder access

        grant_recursive_access(folder)
        return True

    # If a document is provided, ensure the parent folder has access
    if document:
        grant_parent_access(document.folder)

        # Grant direct access to the document itself
        AccessPermission.objects.get_or_create(
            product=product,
            document=document,
            partner2=partner,
            defaults={'partner1': user_company_profile, 'is_direct': True}
        )
        logger.debug(f"Granted access to document: {document} for partner: {partner}")
        return True

    return False


def user_has_access_to(company_profile, obj):
    # If the object is a Product, check direct access
    if isinstance(obj, Product):
        if obj.company == company_profile:
            return True
        return AccessPermission.objects.filter(
            Q(product=obj, partner2=company_profile) | Q(product=obj, partner1=company_profile)
        ).exists()

    # If the object is a Folder, check folder or parent folder access
    if isinstance(obj, Folder):
        if obj.product.company == company_profile:
            return True
        # Check direct folder access
        if AccessPermission.objects.filter(
            Q(folder=obj, partner2=company_profile) | Q(folder=obj, partner1=company_profile)
        ).exists():
            return True
        # Recursively check parent folder access
        if obj.parent and user_has_access_to(company_profile, obj.parent):
            return True

    # If the object is a Document, check folder or document access
    if isinstance(obj, Document):
        # First, check if the company owns the product
        if obj.folder.product.company == company_profile:
            return True
        # Check direct document access
        if AccessPermission.objects.filter(
            Q(document=obj, partner2=company_profile) | Q(document=obj, partner1=company_profile)
        ).exists():
            return True
        # Check access via the parent folder
        if user_has_access_to(company_profile, obj.folder):
            return True

    return False


def company_has_access_to(company_profile, obj):
    # Check if the company profile is the owner
    if isinstance(obj, Product):
        if obj.company == company_profile:
            return True
        return AccessPermission.objects.filter(
            Q(product=obj, partner2=company_profile) | Q(product=obj, partner1=company_profile)
        ).exists()

    if isinstance(obj, Folder):
        if obj.product.company == company_profile:
            return True
        if obj.partner and obj.partner != company_profile:
            return False
        if AccessPermission.objects.filter(
            Q(folder=obj, partner2=company_profile) | Q(folder=obj, partner1=company_profile)
        ).exists():
            return True
        # Recursively check parent folder access
        if obj.parent and company_has_access_to(company_profile, obj.parent):
            return True
        return False

    if isinstance(obj, Document):
        if obj.folder.product.company == company_profile:
            return True
        if obj.partner and obj.partner != company_profile:
            return False
        if AccessPermission.objects.filter(
            Q(document=obj, partner2=company_profile) | Q(document=obj, partner1=company_profile)
        ).exists():
            return True
        # Check if any version is accessible to the partner
        versions = obj.versions.filter(Q(partner=company_profile) | Q(partner__isnull=True))
        if versions.exists():
            return True
        # Check access via the parent folder
        if company_has_access_to(company_profile, obj.folder):
            return True
        return False

    return False