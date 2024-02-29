#invitations/views.py
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from .forms import InvitationForm
from .models import Invitation
from partners.models import Partnership
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404



User = get_user_model()


def send_invitation(request):
    if request.method == 'POST':
        form = InvitationForm(request.POST, request=request)
        if form.is_valid():
            invitation = form.save(commit=False)
            invitation.sender = request.user
            invitation.save()
            # Send email
            send_mail(
                'You are invited!',
                f'Please accept the invitation by visiting: http://127.0.0.1:8000/invitations/accept/{invitation.token}',
                settings.DEFAULT_FROM_EMAIL,
                [invitation.email],
                fail_silently=False,
            )
            messages.success(request, 'Invitation sent successfully.')
            return redirect('partners:partner_list')  # Update this to the correct URL name for your partner list page
        else:
            # If form is not valid, render the partner_list page and pass the invalid form
            messages.error(request, 'There was an error sending the invitation.')
            return render(request, 'partners/partner_list.html', {'form': form})
    else:
        # If accessing this URL directly, you might want to redirect or handle differently
        return render(request, 'partners/partner_list.html', {'form': form})
    

def accept_invitation(request, token):
    try:
        invitation = Invitation.objects.get(token=token, accepted=False)
    except Invitation.DoesNotExist:
        messages.error(request, 'Invalid or expired invitation token.')
        return redirect('home')  # Adjust as needed

    email = invitation.email
    user = User.objects.filter(email=email).first()

    if user:
        if request.user.is_authenticated and request.user == user:
            # User is logged in and matches the invited user
            # Create or update partnership
            partnership, created = Partnership.objects.get_or_create(exporter=invitation.sender, importer=user)
            if not created:
                partnership.is_active = True  # Reactivate the partnership if it was previously deactivated
                partnership.save()

            invitation.accepted = True
            invitation.save()
            messages.success(request, 'Invitation accepted. You are now partners.')
            return redirect('partners:partner_list')
        else:
            # User exists but is not logged in, redirect to login with next parameter
            login_url = f"{reverse('account_login')}?next={reverse('invitations:accept_invitation', kwargs={'token': token})}"
            return redirect(login_url)
    else:
        # User doesn't exist, redirect to signup
        signup_url = f"{reverse('account_signup')}?email={email}"
        return redirect(signup_url)


@login_required
def invitation_list(request):
    received_invitations = Invitation.objects.filter(email=request.user.email)
    sent_invitations = Invitation.objects.filter(sender=request.user)

    context = {
        'received_invitations': received_invitations,
        'sent_invitations': sent_invitations,
    }
    return render(request, 'invitations/invitation_list.html', context)


@login_required
@require_POST
def delete_invitation(request, invitation_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=403)

    try:
        invitation = get_object_or_404(Invitation, id=invitation_id, sender=request.user)
        invitation.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        # Log the error for debugging
        print(f"Error deleting invitation: {e}")
        return JsonResponse({'success': False, 'error': 'Internal Server Error'}, status=500)
