from django.shortcuts import render
from .models import Partnership
from access_control.models import AccessPermission
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.db.models import Q
from invitations.models import Invitation


@login_required
def partner_list_view(request):
    user = request.user
    # Fetch partnerships where the user is either the importer or the exporter
    active_partnerships = Partnership.objects.filter(
        Q(exporter=user) | Q(importer=user),
        is_active=True
    ).distinct()

    received_invitations = Invitation.objects.filter(email=user.email)
    sent_invitations = Invitation.objects.filter(sender=user)

    context = {
        'partnerships': active_partnerships,
        'received_invitations': received_invitations,
        'sent_invitations': sent_invitations,
    }
    return render(request, 'partners/partner_list.html', context)

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
