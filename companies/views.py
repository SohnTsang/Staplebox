import logging
from django.shortcuts import render, redirect, get_object_or_404
from .forms import CompanyProfileForm
from .models import CompanyProfile
from django.contrib.auth.decorators import login_required
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import TemplateHTMLRenderer, JSONRenderer
from rest_framework.permissions import IsAuthenticated
from .serializers import CompanyProfileSerializer
from rest_framework import status
from django.utils.decorators import method_decorator
from django.contrib import messages
from .forms import CompanySelectionForm
from django.db import transaction
from django.core.signing import Signer, BadSignature
from partners.models import Partnership
from django.db.models import Count
from django.db.models import Q
from users.utils import log_user_activity

logger = logging.getLogger(__name__)

signer = Signer()


class ShowCompanyTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user_profile = request.user.userprofile

        try:
            # Unsign the company UUID
            unsigned_company_uuid = signer.unsign(kwargs.get('company_uuid'))
        except BadSignature:
            logger.error("Invalid company UUID signature.")
            return Response({'error': 'Invalid company UUID signature.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            company = get_object_or_404(CompanyProfile, uuid=unsigned_company_uuid)
        except CompanyProfile.DoesNotExist:
            logger.error(f"CompanyProfile with UUID {unsigned_company_uuid} does not exist.")
            return Response({'error': 'Company not found.'}, status=status.HTTP_404_NOT_FOUND)

        if company in user_profile.company_profiles.all():
            logger.info(f"User {request.user.username} accessed invite token for company {company.name}.")
            print(company.max_token_uses, company.token_uses)
            return Response({
                'invite_token': company.invite_token,
                'token_uses': company.token_uses,
                'max_token_uses': company.max_token_uses,
            }, status=status.HTTP_200_OK)
        else:
            logger.warning(f"User {request.user.username} attempted to access invite token for company {company.name} without permission.")
            return Response({'error': 'You do not have permission to view this token.'}, status=status.HTTP_403_FORBIDDEN)


class ShowLinkedUsersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user_profile = request.user.userprofile

        try:
            # Unsign the company UUID
            unsigned_company_uuid = signer.unsign(kwargs.get('company_uuid'))
        except BadSignature:
            logger.error("Invalid company UUID signature.")
            return Response({'error': 'Invalid company UUID signature.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            company = get_object_or_404(CompanyProfile, uuid=unsigned_company_uuid)
        except CompanyProfile.DoesNotExist:
            logger.error(f"CompanyProfile with UUID {unsigned_company_uuid} does not exist.")
            return Response({'error': 'Company not found.'}, status=status.HTTP_404_NOT_FOUND)

        if company in user_profile.company_profiles.all():
            logger.info(f"User {request.user.username} accessed linked users for company {company.name}.")
            users = company.user_profiles.all().values('user__email', 'user__username')
            user_list = [{'email': user['user__email'], 'name': f"{user['user__username']}"} for user in users]

            return Response({'users': user_list}, status=status.HTTP_200_OK)
        else:
            logger.warning(f"User {request.user.username} attempted to access linked users for company {company.name} without permission.")
            return Response({'error': 'You do not have permission to view these users.'}, status=status.HTTP_403_FORBIDDEN)
        

class CompanyProfileView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [TemplateHTMLRenderer, JSONRenderer]
    template_name = 'companies/company_profile.html'

    def get(self, request):
        user_profile = request.user.userprofile
        company_profile = user_profile.company_profiles.first()

        
        if company_profile:
            own_profile = True
            serializer = CompanyProfileSerializer(company_profile)
            signed_company_uuid = signer.sign(str(company_profile.uuid))

            products_count = company_profile.products.count()
            exports_count = company_profile.company_exports.count()
            partnerships_count = company_profile.partnership_as_partner1.count() + company_profile.partnership_as_partner2.count()
            
            recent_products = company_profile.products.all().order_by('-created_at')[:6]
            recent_exports = company_profile.company_exports.filter(completed=False).order_by('export_date')[:6]

            # Annotate partnerships with the total number of exports
            recent_partnerships = Partnership.objects.filter(
                Q(partner1=company_profile) | Q(partner2=company_profile)
            ).annotate(
                total_exports=Count('exports', filter=Q(exports__created_by_company=company_profile))
            ).order_by('-total_exports').distinct()[:7]

            signed_recent_products = [
                {'name': product.product_name, 'code': product.product_code, 'uuid': signer.sign(str(product.uuid)), 'created_at': product.created_at}
                for product in recent_products
            ]
            signed_recent_exports = [
                {
                    'reference': export.reference_number, 
                    'partner': f"{export.partner.partner1.name if export.partner.partner2 == company_profile else export.partner.partner2.name}", 
                    'date': export.export_date, 'uuid': signer.sign(str(export.uuid))
                }
                for export in recent_exports
            ]
            signed_recent_partnerships = [
                {
                    'partners': f"{partnership.partner1.name if partnership.partner2 == company_profile else partnership.partner2.name}",
                    'uuid': signer.sign(str(partnership.uuid)),
                    'total_exports': partnership.total_exports
                }
                for partnership in recent_partnerships
            ]

            context = {
                'company_profile': serializer.data,
                'signed_company_uuid': signed_company_uuid,
                'active_page': 'Company',
                'own_profile': own_profile,
                'is_partner_profile': False,  # Not a partner profile since it's the user's own profile
                'products_count': products_count,
                'exports_count': exports_count,
                'partnerships_count': partnerships_count,
                'recent_products': signed_recent_products,
                'recent_exports': signed_recent_exports,
                'recent_partnerships': signed_recent_partnerships,

            }
        else:
            context = {
                'company_profile': None,
                'signed_company_uuid': None,
                'active_page': 'Company',
                'own_profile': False,
                'is_partner_profile': False
            }

        return Response(context, template_name=self.template_name)


class LinkUserToCompanyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        token = request.data.get('token')
        user_profile = request.user.userprofile

        logger.debug(f"Received token: {token} for user: {request.user}")

        try:
            company = CompanyProfile.objects.get(invite_token=token)
            logger.debug(f"Found company with token: {company.name}")

            if company.can_use_token():
                # Link the company to the user's profile
                user_profile.company_profiles.add(company)
                company.use_token()

                # Log the activity
                log_user_activity(
                    user=request.user,
                    action=f"Linked to company {company.name}",
                    activity_type="PROFILE_UPDATE"
                )

                logger.info(f"User {request.user} successfully linked to company {company.name}")
                return Response({'message': 'Company linked successfully.'}, status=status.HTTP_200_OK)
            else:
                logger.warning(f"Token usage limit reached for company {company.name}")
                return Response({'error': 'Token usage limit reached.'}, status=status.HTTP_400_BAD_REQUEST)
        except CompanyProfile.DoesNotExist:
            logger.error(f"Invalid token: {token}")
            return Response({'error': 'Invalid token.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(f"Unexpected error linking user {request.user} to company.")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

@method_decorator(login_required, name='dispatch')
class EditCompanyProfileView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'companies/company_profile_edit.html'

    def get(self, request):
        user_profile = request.user.userprofile
        company_profile = user_profile.company_profiles.first()
        form = CompanyProfileForm(instance=company_profile)
        return Response({'form': form, 'company_profile': company_profile}, template_name=self.template_name)

    def post(self, request):
        user_profile = request.user.userprofile
        company_profile = user_profile.company_profiles.first() if user_profile.company_profiles.exists() else None

        logger.info(f"POST data received: {request.POST}")
        logger.info(f"FILES data received: {request.FILES}")

        form = CompanyProfileForm(request.POST, request.FILES, instance=company_profile)  # Include request.FILES

        logger.debug("Starting form validation.")
        
        if form.is_valid():
            logger.debug("Form is valid.")

            # Capture the old values before applying the form changes
            old_values = {field: getattr(company_profile, field) for field in form.changed_data}
            logger.debug(f"Captured old values: {old_values}")

            # Apply the new values to the instance but do not save it yet
            company_profile = form.save(commit=False)

            # Track changes by comparing old values with new values
            changes = []
            for field, old_value in old_values.items():
                new_value = form.cleaned_data.get(field)
                logger.debug(f"Comparing field '{field}': old_value='{old_value}', new_value='{new_value}'")
                if old_value != new_value:
                    changes.append(f"{field.capitalize()} changed from '{old_value}' to '{new_value}'")

            # Log the detected changes
            if changes:
                logger.debug(f"Detected changes: {changes}")
            else:
                logger.debug("No changes detected.")

            # Ensure the profile image is being handled
            if 'profile_image' in request.FILES:
                logger.debug(f"Profile image uploaded: {request.FILES['profile_image'].name}")
                company_profile.profile_image = request.FILES['profile_image']
            
            # Save the updated company profile
            company_profile.save()
            logger.debug(f"Final saved state of company_profile: {company_profile.__dict__}")

            if not user_profile.company_profiles.exists():
                user_profile.company_profiles.add(company_profile)
                logger.info(f"Adding new profile for user {request.user.username}")
                messages.success(request, 'Company profile created successfully.')

                # Log the activity for profile creation
                log_user_activity(
                    user=request.user,
                    action=f"Created company profile {company_profile.name}",
                    activity_type="PROFILE_UPDATE"
                )

            else:
                logger.info(f"Updating existing profile for user {request.user.username}")
                messages.success(request, 'Company profile updated successfully.')

                if changes:
                    # Log the activity with specific field changes
                    log_user_activity(
                        user=request.user,
                        action=f"Updated company profile {company_profile.name}: " + "; ".join(changes),
                        activity_type="PROFILE_UPDATE"
                    )

            return redirect('companies:company_profile_view')
        else:
            logger.error(f"Form submission errors: {form.errors}")
            messages.error(request, 'Please correct the errors below.')
            return Response({'form': form, 'company_profile': company_profile}, template_name=self.template_name)
    