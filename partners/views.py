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


@login_required
def partner_list_view(request):
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
            return JsonResponse({'error': 'Invalid type specified'}, status=400)
        
        invitations = invitations_query[start:start+limit]
        has_more = invitations_query.count() > start + limit

        
        # Convert invitations to a list of dicts to serialize them
        data = []
        for invitation in invitations:
            data.append({
                'id': invitation.id,
                'email': invitation.email if type == 'sent' else invitation.sender.email,
                'accepted': invitation.accepted,
                'created_at': invitation.created_at.strftime('%H:%M, %Y-%b-%d '),
            })

        return JsonResponse({
            'invitations': data,
            'has_more': has_more,
        })
    
    # Check if there are errors in the session
    form_errors = request.session.pop('form_errors', None)
    
    # Initialize form
    form = InvitationForm(request=request) if not form_errors else InvitationForm(request=request, data=request.session.pop('form_data', {}))


    if request.method == 'POST':
        form = InvitationForm(request.POST, request=request)
        if form.is_valid():

            user_profile = request.user.userprofile

            company_profile, created = CompanyProfile.objects.get_or_create(user_profile=user_profile)

            # Check if the user's company profile is complete
            if not company_profile.name or not company_profile.role:
                messages.error(request, "Please complete your company profile before adding partners.")
                return redirect('partners:partner_list')
            
            email = form.cleaned_data['email']

            if Invitation.objects.filter(sender=user, email=email, accepted=False).exists():
                messages.error(request, f"Invitation to {email} is already pending.")
                return redirect('partners:partner_list')
            elif Partnership.objects.filter(Q(partner1=user, partner2__email=email) | Q(partner2=user, partner1__email=email)).exists():
                messages.error(request, f"A partnership with {email} already exists.")
                return redirect('partners:partner_list')
            elif Partnership.objects.filter(Q(partner1=user, partner2__email=email) | Q(partner2=user, partner1__email=email)).exists():
                messages.error(request, f"A partnership with {email} already exists.")
                return redirect('partners:partner_list')
            elif not User.objects.filter(email=email).exists():
                messages.error(request, "The user with this email does not exist.")
                return redirect('partners:partner_list')
            
            invitation = form.save(commit=False)
            invitation.sender = user
            # Prevent sending to self logic here
            invitation.save()
            send_mail(
                    'You are invited!',
                    f'Please accept the invitation by visiting: http://127.0.0.1:8000/invitations/accept/{invitation.token}',
                    settings.DEFAULT_FROM_EMAIL,
                    [invitation.email],
                    fail_silently=False,
                )
            messages.success(request, 'Invitation sent successfully.', extra_tags='invitation_action')
            return redirect('partners:partner_list')
        else:
            # Store form errors and form data in the session
            request.session['form_errors'] = form.errors.as_json()
            request.session['form_data'] = request.POST
            return redirect('partners:partner_list')

    active_partnerships = Partnership.objects.filter(Q(partner1=user) | Q(partner2=user), is_active=True).distinct()
    partner_info = []
    received_invitations = Invitation.objects.filter(email=user.email).order_by('-created_at')[:5]
    sent_invitations = Invitation.objects.filter(sender=user).order_by('-created_at')[:5]


    partners = set()
    
    #for partnership in active_partnerships:
    #    partners.add(partnership.partner1.email)
    #    partners.add(partnership.partner2.email)
    for partnership in active_partnerships:

        partners.add(partnership.partner1.email)
        partners.add(partnership.partner2.email)

        partner_user = partnership.partner2 if partnership.partner1 == user else partnership.partner1
        try:
            company_profile = CompanyProfile.objects.get(user_profile=partner_user.userprofile)
            partner_info.append({'id': partnership.id, 'email': partner_user.email, 'created_at': partnership.created_at, 'company_name': company_profile.name, 'company_email': company_profile.email, 'company_role': company_profile.role})
        except CompanyProfile.DoesNotExist:
            partner_info.append({'email': partner_user.email, 'created_at': partnership.created_at, 'company_name': 'No company profile'})

        # Delete sent invitations if the user is already a partner with the recipient
        for invitation in sent_invitations:
            if invitation.email in partners:
                invitation.delete()
    

    # Now check if there are more than 5 invitations to decide whether to show "See More" buttons
    has_received_pending_invitations = Invitation.objects.filter(email=user.email, accepted=False)
    has_more_received_pending_invitations = Invitation.objects.filter(email=user.email, accepted=False).count() > 5
    has_more_sent_invitations = Invitation.objects.filter(sender=user).count() > 5


    context = {
        'form': form,
        'partnerships': active_partnerships,
        'partner_info': partner_info,
        'received_invitations': received_invitations,
        'sent_invitations': sent_invitations,
        'has_more_received_pending_invitations': has_more_received_pending_invitations,
        'has_received_pending_invitations': has_received_pending_invitations,
        'has_more_sent_invitations': has_more_sent_invitations,
        'form_errors': form_errors,  # Pass any errors to the template
        'current_page': 'partners',
    }
    return render(request, 'partners/partner_list.html', context)


def get_invitations(queryset, start=0, limit=5):
    """
    Helper function to fetch invitations with pagination.
    """
    end = start + limit
    invitations = queryset[start:end]
    has_more = queryset.count() > end
    return invitations, has_more

@login_required
@require_POST
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

            return JsonResponse({'success': True})
        else:
            return JsonResponse({'error': 'You do not have permission to delete this partner.'}, status=403)
    except Exception as e:
        print(f"Error deleting partner: {e}")
        return JsonResponse({'success': False, 'error': 'Internal Server Error'}, status=500)
