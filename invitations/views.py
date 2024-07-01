#invitations/views.py
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
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
from django.db.models import Q
from .serializers import InvitationSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

class SendInvitation(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        logger.debug("Received data for invitation: %s", request.data)
        serializer = InvitationSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            invitation = serializer.save()
            logger.info("Invitation created: %s", invitation)
            # Send email
            send_mail(
                'You are invited!',
                f'Please accept the invitation by visiting: {request.build_absolute_uri(reverse('invitations:accept_invitation', kwargs={'token': invitation.token}))}',
                settings.DEFAULT_FROM_EMAIL,
                [invitation.email],
                fail_silently=False,
            )
            return Response({'message': 'Invitation sent'}, status=status.HTTP_201_CREATED)
        else:
            logger.error("Errors in invitation form: %s", serializer.errors)
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        

class AcceptInvitation(APIView):
    def get(self, request, token, *args, **kwargs):
        try:
            invitation = get_object_or_404(Invitation, token=token, accepted=False)
        except Invitation.DoesNotExist:
            if request.accepts('application/json'):
                return Response({'error': 'Invalid or expired invitation token.'}, status=status.HTTP_404_NOT_FOUND)
            else:
                messages.error(request, 'Invalid or expired invitation token.')
                return redirect('home')

        user = User.objects.filter(email=invitation.email).first()
        if user:
            if request.user.is_authenticated and request.user == user:
                partnership, created = Partnership.objects.get_or_create(partner1=invitation.sender, partner2=user)
                if not created:
                    partnership.is_active = True
                    partnership.save()
                invitation.accepted = True
                invitation.save()
                if request.accepts('application/json'):
                    return Response({'message': 'Invitation accepted. You are now partners.'}, status=status.HTTP_200_OK)
                else:
                    messages.success(request, 'Invitation accepted. You are now partners.')
                    return redirect('partners:partner_list')
            else:
                login_url = f"{reverse('account_login')}?next={reverse('invitations:accept_invitation', kwargs={'token': token})}"
                return redirect(login_url)
        else:
            signup_url = f"{reverse('account_signup')}?email={invitation.email}"
            return redirect(signup_url)


class DeleteInvitation(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, invitation_id):
        invitation = get_object_or_404(Invitation, id=invitation_id, sender=request.user)
        invitation.delete()
        return Response({'message': 'Invitation deleted'}, status=status.HTTP_204_NO_CONTENT)

    def delete(self, request, invitation_id):
        # This method explicitly handles DELETE requests if needed
        invitation = get_object_or_404(Invitation, id=invitation_id, sender=request.user)
        invitation.delete()
        return Response({'message': 'Invitation deleted'}, status=status.HTTP_200_OK)
