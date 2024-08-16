from django.db.models import Count
from .models import Product, Folder, Document, AccessPermission
from companies.models import CompanyProfile
from users.models import User
from django.db.models import Q
from rest_framework.response import Response
from rest_framework import status

class AccessControlMixin:
    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object_to_check(request, *args, **kwargs)
        if not obj or not self.has_access(request.user, obj):
            return self.handle_permission_denied(request)
        return super().dispatch(request, *args, **kwargs)

    def get_object_to_check(self, request, *args, **kwargs):
        raise NotImplementedError("Must override get_object_to_check method")

    def has_access(self, user, obj):
        # By default, check using user_has_access_to
        return user_has_access_to(user, obj)

    def handle_permission_denied(self, request):
        # This function is called when permission is denied
        response = Response({'error': 'You do not have access to this function'}, status=status.HTTP_403_FORBIDDEN)
        self._set_renderer_and_accept_language(request, response)
        return response

    def _set_renderer_and_accept_language(self, request, response):
        """
        Set renderer and language for the response.
        """
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
        """
        Select an appropriate renderer based on the request.
        """
        return request.accepted_renderer if hasattr(request, 'accepted_renderer') else self.get_renderers()[0]
    

def get_partners_with_access(product):
    permissions = AccessPermission.objects.filter(product=product).select_related('partner2').prefetch_related('folder', 'document')

    permissions = permissions.values('partner2').annotate(
        folder_count=Count('folder', distinct=True),
        document_count=Count('document', distinct=True)
    )

    partners_with_access = []
    total_folders = Folder.objects.filter(product=product).exclude(name='Root').count()
    total_documents = Document.objects.filter(folder__product=product).count()

    for permission in permissions:
        partner = CompanyProfile.objects.get(id=permission['partner2'])

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
            'company_name': partner.name,
            'company_email': partner.email,
            'company_role': partner.role,
            'partner2_id': partner.id,
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
    product_access_exists = AccessPermission.objects.filter(
        Q(partner2=partner) | Q(partner1=partner),
        product=product,
        folder__isnull=True,
        document__isnull=True
    ).exists()

    if product_access_exists:
        return False

    if folder:
        if folder.is_root:
            return grant_product_access(user_company_profile, partner, product)
        
        current_folder = folder.parent
        while current_folder:
            if AccessPermission.objects.filter(
                Q(partner2=partner) | Q(partner1=partner),
                product=product,
                folder=current_folder
            ).exists():
                return False
            current_folder = current_folder.parent

        def grant_recursive_access(current_folder):
            AccessPermission.objects.get_or_create(
                product=product,
                folder=current_folder,
                partner2=partner,
                defaults={'partner1': user_company_profile}
            )
            for doc in current_folder.documents.all():
                AccessPermission.objects.get_or_create(
                    product=product,
                    document=doc,
                    partner2=partner,
                    defaults={'partner1': user_company_profile}
                )
            for subfolder in current_folder.subfolders.all():
                grant_recursive_access(subfolder)

        grant_recursive_access(folder)
        return True

    if document:
        folder_access_exists = AccessPermission.objects.filter(
            Q(partner2=partner) | Q(partner1=partner),
            product=product,
            folder=document.folder
        ).exists()

        if folder_access_exists:
            return False
        
        AccessPermission.objects.get_or_create(
            product=product,
            document=document,
            partner2=partner,
            defaults={'partner1': user_company_profile}
        )
        return True

    return False


def user_has_access_to(user_company_profile, obj):
    if user_company_profile.is_superuser:
        return True

    if isinstance(obj, Product):
        if obj.user == user_company_profile:
            return True
        return AccessPermission.objects.filter(
            Q(product=obj, partner2=user_company_profile) | Q(product=obj, partner1=user_company_profile)
        ).exists()

    if isinstance(obj, Folder):
        if obj.product.user == user_company_profile:
            return True
        if AccessPermission.objects.filter(
            Q(folder=obj, partner2=user_company_profile) | Q(folder=obj, partner1=user_company_profile)
        ).exists():
            return True
        for doc in Document.objects.filter(folder=obj):
            if user_has_access_to(user_company_profile, doc):
                return True

    if isinstance(obj, Document):
        if obj.folder.product.user == user_company_profile:
            return True
        if AccessPermission.objects.filter(
            Q(document=obj, partner2=user_company_profile) | Q(document=obj, partner1=user_company_profile)
        ).exists():
            current_folder = obj.folder
            while current_folder:
                AccessPermission.objects.get_or_create(
                    partner1=AccessPermission.objects.filter(
                        Q(product=current_folder.product, partner2=user_company_profile) | Q(product=current_folder.product, partner1=user_company_profile)
                    ).first().partner1,
                    partner2=user_company_profile,
                    product=current_folder.product,
                    folder=current_folder,
                )
                current_folder = current_folder.parent
            return True

    return False