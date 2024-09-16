from django.shortcuts import redirect
from .models import Partnership
from users.models import User
from companies.models import CompanyProfile
from access_control.models import AccessPermission
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db.models import Q, Prefetch
from invitations.models import Invitation
from django.contrib import messages
from invitations.forms import InvitationForm
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from .models import Partnership
from companies.models import CompanyProfile
from documents.models import Document
from .serializers import PartnershipSerializer, InvitationSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils.decorators import method_decorator
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.permissions import IsAuthenticated
from django.views.decorators.http import require_http_methods
from django.core.signing import Signer, BadSignature

import logging

signer = Signer()

logger = logging.getLogger(__name__)


@method_decorator(login_required, name='dispatch')
class PartnerCompanyProfileView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'companies/company_profile.html'

    def get(self, request, partner_uuid):
        logger.debug(f"Received partner_uuid: {partner_uuid}")
        try:
            unsigned_partner_uuid = signer.unsign(partner_uuid)
            logger.debug(f"Unsigned partner_uuid: {unsigned_partner_uuid}")
        except BadSignature:
            logger.error("Invalid partner ID signature")
            return Response({"detail": "Invalid partner ID."}, status=400)

        partnership = get_object_or_404(Partnership, uuid=unsigned_partner_uuid)
        logger.debug(f"Partnership found: {partnership.partner1.name} - {partnership.partner2.name}")

        user_company_profiles = request.user.userprofile.company_profiles.all()
        if not any(profile in user_company_profiles for profile in [partnership.partner1, partnership.partner2]):
            logger.warning(f"User {request.user.username} is not authorized to view this page.")
            return Response({"detail": "You are not authorized to view this page."}, status=403)

        viewing_partner = partnership.partner2 if partnership.partner1 in user_company_profiles else partnership.partner1
        logger.debug(f"Viewing partner: {viewing_partner.name}")

        company_profile = get_object_or_404(CompanyProfile, uuid=viewing_partner.uuid)
        logger.debug(f"CompanyProfile found: {company_profile.name}")

        # Log the profile image URL
        if company_profile.profile_image:
            logger.debug(f"Partner's profile image URL: {company_profile.profile_image.url}")
        else:
            logger.debug("Partner's profile image not found. Using default image.")

        folder = partnership.shared_folder
        if not folder:
            logger.error("No shared folder found for this partnership.")
            return Response({"detail": "No shared folder found for this partnership."}, status=404)

        documents = Document.objects.filter(folder=folder).distinct()
        signed_documents = [{
            'uuid': signer.sign(str(document.uuid)),
            'original_filename': document.original_filename,
            'comments': document.comments,
            'uploaded_by': document.uploaded_by.userprofile.company_profiles.first() if document.uploaded_by.userprofile.company_profiles.exists() else document.uploaded_by.username,
        } for document in documents]

        logger.info(f"User {request.user.username} viewed partner company profile for {company_profile.name}.")
        return Response({
            'company_profile': company_profile,
            'documents': signed_documents,
            'folder_id': signer.sign(str(folder.uuid)) if folder else None,
            'is_partner_profile': True
        }, template_name=self.template_name)




@method_decorator(login_required, name='dispatch')
class PartnerListView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'partners/partner_list.html'

    def get(self, request):
        user = request.user
        user_profile = user.userprofile
        user_company_profiles = user_profile.company_profiles.all()
        company_email = user_company_profiles.first().email if user_company_profiles.exists() else None

        # Get all user emails associated with the company profile
        user_emails = list(User.objects.filter(userprofile__company_profiles__in=user_company_profiles).values_list('email', flat=True))

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            type = request.GET.get('type', None)  # 'received' or 'sent'
            start = int(request.GET.get('start', 0))
            limit = 5

            if type == 'received' and company_email:
                invitations_query = Invitation.objects.filter(
                    Q(email__in=user_emails) | Q(email=company_email)
                ).order_by('-created_at')
            elif type == 'sent' and user_company_profiles.exists():
                invitations_query = Invitation.objects.filter(
                    sender__in=user_company_profiles
                ).order_by('-created_at')
            else:
                return Response({'error': 'Invalid type specified'}, status=status.HTTP_400_BAD_REQUEST)

            invitations, has_more = self.get_invitations(invitations_query, start, limit)
            data = InvitationSerializer(invitations, many=True).data

            return Response({
                'invitations': data,
                'has_more': has_more,
            })

        form_errors = request.session.pop('form_errors', None)
        form = InvitationForm(request=request) if not form_errors else InvitationForm(request=request, data=request.session.pop('form_data', {}))

        filter_value = request.GET.get('filter_value', '')
        filter_type = request.GET.get('filter_type', 'company_name')

        if user_company_profiles.exists():
            company_email = user_company_profiles.first().email
            active_partnerships = Partnership.objects.filter(
                (Q(partner1__in=user_company_profiles) | Q(partner2__in=user_company_profiles)),
                is_active=True
            ).distinct()
        else:
            active_partnerships = Partnership.objects.none()

        partner_info = []
        filtered_partnerships = []

        received_invitations = Invitation.objects.filter(
            Q(email__in=user_emails) | Q(email=company_email)
        ).order_by('-created_at')[:5] if company_email else []

        sent_invitations = Invitation.objects.filter(sender=user).order_by('-created_at')[:5]


        for partnership in active_partnerships:
            partner_profile = partnership.partner2 if partnership.partner1 in user_company_profiles else partnership.partner1
            should_add = False
            if filter_type == 'company_name' and filter_value.lower() in partner_profile.name.lower():
                should_add = True
            elif filter_type == 'email' and filter_value.lower() in partner_profile.email.lower():
                should_add = True
            elif filter_type == 'role' and partner_profile.role and filter_value.lower() in partner_profile.role.lower():
                should_add = True
            elif not filter_type:
                should_add = True
            if should_add:
                filtered_partnerships.append(partnership)

        for partnership in filtered_partnerships:
            partner_profile = partnership.partner2 if partnership.partner1 in user_company_profiles else partnership.partner1
            partner_info.append({
                'id': signer.sign(str(partnership.uuid)),  # Use signed UUID
                'email': partner_profile.email,
                'created_at': partnership.created_at.strftime('%Y-%m-%d'),
                'company_name': partner_profile.name,
                'company_email': partner_profile.email,
                'company_role': partner_profile.role,
            })

        has_received_pending_invitations = Invitation.objects.filter(
            Q(email__in=user_emails) | Q(email=company_email), accepted=False
        ) if company_email else []
        
        has_more_received_pending_invitations = Invitation.objects.filter(
            Q(email__in=user_emails) | Q(email=company_email), accepted=False
        ).count() > 5 if company_email else False
        
        has_more_sent_invitations = Invitation.objects.filter(sender=user).count() > 5
        unaccepted_invitations_count = Invitation.objects.filter(
            Q(email__in=user_emails) | Q(email=company_email), accepted=False
        ).count() if company_email else 0

        context = {
            'form': form.as_p(),  # Convert form to HTML
            'partnerships': PartnershipSerializer(active_partnerships, many=True).data,
            'partner_info': partner_info,
            'received_invitations': InvitationSerializer(received_invitations, many=True).data,
            'sent_invitations': InvitationSerializer(sent_invitations, many=True).data,
            'has_more_received_pending_invitations': has_more_received_pending_invitations,
            'has_received_pending_invitations': has_received_pending_invitations,
            'has_more_sent_invitations': has_more_sent_invitations,
            'form_errors': form_errors,
            'current_page': 'partners',
            'active_page': 'Partners',
            'partner_count': len(partner_info),  # Add the count of partners
            'unaccepted_invitations_count': unaccepted_invitations_count,  # Pass the count to the template
        }


        return Response(context, template_name=self.template_name)

    def post(self, request):
        form = InvitationForm(request.POST, request=request)
        if form.is_valid():
            user_profile = request.user.userprofile
            company_profile, created = CompanyProfile.objects.get_or_create(user_profiles=user_profile)

            if not company_profile.name or not company_profile.role:
                messages.error(request, "Please complete your company profile before adding partners.")
                return redirect('partners:partner_list')

            email = form.cleaned_data['email']

            if Invitation.objects.filter(sender=request.user, email=email, accepted=False).exists():
                messages.error(request, f"Invitation to {email} is already pending.")
                return redirect('partners:partner_list')
            elif Partnership.objects.filter(Q(partner1=request.user, partner2__email=email) | Q(partner2=request.user, partner1__email=email)).exists():
                messages.error(request, f"A partnership with {email} already exists.")
                return redirect('partners:partner_list')
            elif not User.objects.filter(email=email).exists():
                messages.error(request, "The user with this email does not exist.")
                return redirect('partners:partner_list')

            invitation = form.save(commit=False)
            invitation.sender = request.user
            invitation.token = signer.sign(str(invitation.token))
            invitation.save()
            send_mail(
                'You are invited!',
                f'Please accept the invitation by visiting: http://127.0.0.1:8000/invitations/accept/{invitation.token}',
                settings.DEFAULT_FROM_EMAIL,
                [invitation.email],
                fail_silently=False,
            )
            messages.success(request, 'Invitation sent', extra_tags='invitation_action')
            return redirect('partners:partner_list')
        else:
            request.session['form_errors'] = form.errors.as_json()
            request.session['form_data'] = request.POST
            return redirect('partners:partner_list')

    def get_invitations(self, queryset, start=0, limit=5):
        end = start + limit
        invitations = queryset[start:end]
        has_more = queryset.count() > end
        return invitations, has_more

    
@login_required
@require_http_methods(["POST", "DELETE"])
def delete_partner(request, partner_uuid):
    try:
        unsigned_partner_uuid = signer.unsign(partner_uuid)
        partner = get_object_or_404(Partnership, uuid=unsigned_partner_uuid)
        
        # Check if the current user is part of the partnership
        if request.user == partner.partner1 or request.user == partner.partner2:
            # Identify the other user in the partnership
            other_user = partner.partner2 if request.user == partner.partner1 else partner.partner1

            # Delete the partnership
            partner.delete()

            # Remove related access permissions for any direction of the partnership
            AccessPermission.objects.filter(
                (Q(partner1=request.user) & Q(partner2=other_user)) |
                (Q(partner2=request.user) & Q(partner1=other_user))
            ).delete()

            return JsonResponse({'message': 'Partner deleted'}, status=200)
        else:
            return JsonResponse({'error': 'You do not have permission to delete this partner'}, status=403)
    except BadSignature:
        raise Http404("Invalid partner UUID")
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



