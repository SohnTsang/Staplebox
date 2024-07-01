from django.shortcuts import render, redirect
from .models import Partnership
from users.models import User
from companies.models import CompanyProfile
from access_control.models import AccessPermission
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.db.models import Q
from invitations.models import Invitation
from django.contrib import messages
from invitations.forms import InvitationForm
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from .models import Partnership
from companies.models import CompanyProfile
from documents.models import Document
from django.http import HttpResponseForbidden
from .serializers import PartnershipSerializer, CompanyProfileSerializer, InvitationSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils.decorators import method_decorator
from rest_framework.renderers import TemplateHTMLRenderer
from documents.serializers import DocumentSerializer
from rest_framework.permissions import IsAuthenticated
from django.views.decorators.http import require_http_methods


@method_decorator(login_required, name='dispatch')
class PartnerCompanyProfileView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'companies/company_profile.html'

    def get(self, request, partner_id):
        partnership = get_object_or_404(Partnership, pk=partner_id)

        if request.user not in [partnership.partner1, partnership.partner2]:
            return Response({"detail": "You are not authorized to view this page."}, status=403)

        # Determine the "other partner" based on the current user
        viewing_partner = partnership.partner2 if request.user == partnership.partner1 else partnership.partner1

        # Get company profiles for both partners
        company_profile = get_object_or_404(CompanyProfile, user_profile=viewing_partner.userprofile)
        user_company_profile = get_object_or_404(CompanyProfile, user_profile=request.user.userprofile)

        # Get folders for both company profiles
        folders = [company_profile.partners_contract_folder, user_company_profile.partners_contract_folder]
        documents = Document.objects.filter(folder__in=folders).distinct()

        # Ensure context is compatible with template requirements
        return Response({
            'company_profile': company_profile,
            'documents': documents,
            'folder_id': company_profile.partners_contract_folder.id if company_profile.partners_contract_folder else None,
        }, template_name=self.template_name)



@method_decorator(login_required, name='dispatch')
class PartnerListView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'partners/partner_list.html'

    def get(self, request):
        user = request.user

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            type = request.GET.get('type', None)  # 'received' or 'sent'
            start = int(request.GET.get('start', 0))
            limit = 5

            if type == 'received':
                invitations_query = Invitation.objects.filter(email=user.email).order_by('-created_at')
            elif type == 'sent':
                invitations_query = Invitation.objects.filter(sender=user).order_by('-created_at')
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

        active_partnerships = Partnership.objects.filter(Q(partner1=user) | Q(partner2=user), is_active=True).distinct()
        partner_info = []
        filtered_partnerships = []

        received_invitations = Invitation.objects.filter(email=user.email).order_by('-created_at')[:5]
        sent_invitations = Invitation.objects.filter(sender=user).order_by('-created_at')[:5]

        partners = set()
        for partnership in active_partnerships:
            partner_user = partnership.partner2 if partnership.partner1 == user else partnership.partner1
            partners.add(partner_user.email)

        # Delete sent invitations if the user is already a partner with the recipient
        #for invitation in sent_invitations:
        #    if invitation.email in partners:
        #        invitation.delete()

        for partnership in active_partnerships:
            partner_user = partnership.partner2 if partnership.partner1 == user else partnership.partner1
            try:
                company_profile = CompanyProfile.objects.get(user_profile=partner_user.userprofile)
                should_add = False
                if filter_type == 'company_name' and filter_value.lower() in company_profile.name.lower():
                    should_add = True
                elif filter_type == 'email' and filter_value.lower() in company_profile.email.lower():
                    should_add = True
                elif filter_type == 'role' and filter_value.lower() in company_profile.role.lower():
                    should_add = True
                elif not filter_type:
                    should_add = True
                if should_add:
                    filtered_partnerships.append(partnership)
            except CompanyProfile.DoesNotExist:
                continue

        for partnership in filtered_partnerships:
            partner_user = partnership.partner2 if partnership.partner1 == user else partnership.partner1
            try:
                company_profile = CompanyProfile.objects.get(user_profile=partner_user.userprofile)
                partner_info.append({
                    'id': partnership.id,
                    'email': partner_user.email,
                    'created_at': partnership.created_at.strftime('%Y-%m-%d'),
                    'company_name': company_profile.name,
                    'company_email': company_profile.email,
                    'company_role': company_profile.role,
                })
            except CompanyProfile.DoesNotExist:
                partner_info.append({
                    'id': partnership.id,
                    'email': partner_user.email,
                    'created_at': partnership.created_at.strftime('%d-%b-%Y'),
                    'company_name': 'No company profile',
                    'company_email': '',
                    'company_role': '',
                })

        has_received_pending_invitations = Invitation.objects.filter(email=user.email, accepted=False)
        has_more_received_pending_invitations = Invitation.objects.filter(email=user.email, accepted=False).count() > 5
        has_more_sent_invitations = Invitation.objects.filter(sender=user).count() > 5
        unaccepted_invitations_count = Invitation.objects.filter(email=user.email, accepted=False).count()

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
            company_profile, created = CompanyProfile.objects.get_or_create(user_profile=user_profile)

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
@require_http_methods(["POST", "DELETE"])  # Allow both POST and DELETE
def delete_partner(request, partner_id):
    try:
        partner = get_object_or_404(Partnership, id=partner_id)
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
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
