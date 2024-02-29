from django.shortcuts import render, redirect
from .models import Partnership
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

    active_partnerships = Partnership.objects.filter(Q(exporter=user) | Q(importer=user), is_active=True).distinct()
    received_invitations = Invitation.objects.filter(email=user.email).order_by('-created_at')[:5]
    sent_invitations = Invitation.objects.filter(sender=user).order_by('-created_at')[:5]

    # Now check if there are more than 5 invitations to decide whether to show "See More" buttons
    has_more_received_invitations = Invitation.objects.filter(email=user.email).count() > 5
    has_more_sent_invitations = Invitation.objects.filter(sender=user).count() > 5


    context = {
        'form': form,
        'partnerships': active_partnerships,
        'received_invitations': received_invitations,
        'sent_invitations': sent_invitations,
        'has_more_received_invitations': has_more_received_invitations,
        'has_more_sent_invitations': has_more_sent_invitations,
        'form_errors': form_errors  # Pass any errors to the template
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
        if request.user == partner.exporter or request.user == partner.importer:
            # Identify the other user in the partnership
            other_user = partner.importer if request.user == partner.exporter else partner.exporter
            
            # Delete the partnership
            partner.delete()

            # Remove related access permissions for any direction of the partnership
            AccessPermission.objects.filter(
                (Q(exporter=request.user) & Q(importer=other_user)) |
                (Q(importer=request.user) & Q(exporter=other_user))
            ).delete()

            return JsonResponse({'success': True})
        else:
            return JsonResponse({'error': 'You do not have permission to delete this partner.'}, status=403)
    except Exception as e:
        print(f"Error deleting partner: {e}")
        return JsonResponse({'success': False, 'error': 'Internal Server Error'}, status=500)
