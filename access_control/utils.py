from django.db.models import Count
from .models import Product, Folder, Document, AccessPermission
from companies.models import CompanyProfile
from users.models import User
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import F
from django.db.models import Exists, OuterRef


def get_partners_with_access(product):
    permissions = AccessPermission.objects.filter(product=product).select_related('partner2').prefetch_related('folder', 'document')

    permissions = permissions.values('partner2').annotate(
        folder_count=Count('folder', distinct=True),
        document_count=Count('document', distinct=True)
    )

    partners_with_access = []
    # Exclude the folder named 'Root' from the total count
    total_folders = Folder.objects.filter(product=product).exclude(name='Root').count()
    total_documents = Document.objects.filter(folder__product=product).count()

    for permission in permissions:
        partner = User.objects.get(id=permission['partner2'])  # Get the User instance for 'partner2'
        company_profile = CompanyProfile.objects.filter(user_profile__user=partner).first()

        product_access = AccessPermission.objects.filter(
            partner2=partner,
            product=product,
            folder__isnull=True,
            document__isnull=True
        ).exists()

        access_detail = f"{permission['folder_count']} folders and {permission['document_count']} documents"
        if product_access or (permission['folder_count'] == total_folders and permission['document_count'] == total_documents):
            access_detail = "All folders and documents"

        partners_with_access.append({
            'access_detail': access_detail,
            'company_name': company_profile.name if company_profile else "No Company Profile",
            'company_email': company_profile.email if company_profile else "",
            'company_role': company_profile.role if company_profile else "",
            'partner2_id': partner.id,
        })

    return partners_with_access


def check_and_grant_access(user, partner, product, folder=None, document=None, access_type='read_only'):
    model = Folder if folder else Document
    target = folder if folder else document

    # Checking for higher-level access to avoid redundancy.
    higher_level_access_exists = AccessPermission.objects.filter(
        partner2=partner,
        product=product,
        folder__isnull=True,
        document__isnull=True,
        access_type=access_type
    ).exists()

    if higher_level_access_exists:
        return False  # No need to grant lower-level access

    # Check for existing access at the same level to update or create.
    filter_args = {'partner1': user, 'partner2': partner, 'product': product, 'access_type': access_type}
    if folder:
        filter_args['folder'] = folder
    elif document:
        filter_args['document'] = document
    else:
        # This is for product-level access without specific folder or document
        filter_args['folder__isnull'] = True
        filter_args['document__isnull'] = True

    permission, created = AccessPermission.objects.get_or_create(
        defaults=filter_args,
        **filter_args
    )

    if not created:
        # Update if exists and access type is different
        if permission.access_type != access_type:
            permission.access_type = access_type
            permission.save()

    return created or permission.access_type != access_type



def grant_product_access(user, partner, product):
    # Check if a product-level permission already exists to avoid redundant operations
    existing_permission = AccessPermission.objects.filter(
        product=product, 
        partner1=user, 
        partner2=partner,
        folder__isnull=True, 
        document__isnull=True
    ).first()

    if existing_permission:
        # If it exists, ensure no other permissions exist
        AccessPermission.objects.filter(
            product=product, 
            partner1=user, 
            partner2=partner
        ).exclude(
            id=existing_permission.id
        ).delete()
        return False  # No new permission was created
    else:
        # Create a product-level permission
        permission, created = AccessPermission.objects.get_or_create(
            product=product,
            partner1=user,
            partner2=partner,
            defaults={'folder': None, 'document': None}
        )
        # Ensure no other permissions exist
        if created:
            AccessPermission.objects.filter(
                product=product, 
                partner1=user, 
                partner2=partner
            ).exclude(
                id=permission.id
            ).delete()
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


def user_has_access_to(user, obj):
    """
    Enhanced access check function to ensure users can navigate to accessible documents
    through their parent folders without gaining access to other items in those folders.
    Owners of the product have full access to everything under that product.
    """
    if user.is_superuser:
        return True

    # Access check for Product
    if isinstance(obj, Product):
        # Product owners have full access
        if obj.user == user:
            return True
        return AccessPermission.objects.filter(partner2=user, product=obj).exists()

    # Access check for Folder
    if isinstance(obj, Folder):
        # Owners of the product have full access
        if obj.product.user == user:
            return True
        # Check for direct folder access
        if AccessPermission.objects.filter(partner2=user, folder=obj).exists():
            return True
        # Check if any child document of this folder has access
        return Document.objects.filter(folder=obj).exists() and any(
            user_has_access_to(user, doc) for doc in Document.objects.filter(folder=obj))

    # Access check for Document
    if isinstance(obj, Document):
        # Owners of the product have full access
        if obj.folder.product.user == user:
            return True
        # Check for direct document access
        if AccessPermission.objects.filter(partner2=user, document=obj).exists():
            # Grant access to all parent folders for navigation purposes
            current_folder = obj.folder
            while current_folder:
                AccessPermission.objects.get_or_create(
                    partner1=user,  # Assuming the system or admin user here
                    partner2=user,
                    product=current_folder.product,
                    folder=current_folder,
                    defaults={'access_type': 'navigate'}  # Custom access type for navigation
                )
                current_folder = current_folder.parent
            return True

    return False




