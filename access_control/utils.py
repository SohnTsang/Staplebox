from django.db.models import Count
from .models import Product, Folder, Document, AccessPermission
from companies.models import CompanyProfile
from users.models import User
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse


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


