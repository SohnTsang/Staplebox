#invitations/views.py
from django.shortcuts import render, redirect
from django.urls import reverse
from .models import Invitation
from partners.models import Partnership
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.db.models import Q
from .serializers import InvitationSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import logging
from companies.models import CompanyProfile
from django.core.signing import BadSignature, Signer
import uuid

signer = Signer()

logger = logging.getLogger(__name__)

User = get_user_model()


class SendInvitation(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        logger.debug("Received data for invitation: %s", request.data)
        serializer = InvitationSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            # Convert user email to company profile email if necessary
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
                company_profile = user.userprofile.company_profiles.first()
                if company_profile:
                    email = company_profile.email
                    serializer.validated_data['email'] = email
            except User.DoesNotExist:
                pass
            
            invitation = serializer.save(sender=request.user)
            logger.info("Invitation created: %s", invitation)

            # Send email
            send_mail(
                'You are invited!',
                f'Please accept the invitation by visiting: {request.build_absolute_uri(reverse('invitations:accept_invitation', kwargs={'token': invitation.token}))}',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            return Response({'message': 'Invitation sent'}, status=status.HTTP_201_CREATED)
        else:
            logger.error("Errors in invitation form: %s", serializer.errors)
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        
class AcceptInvitation(APIView):
    def get(self, request, token, *args, **kwargs):
        try:
            logger.debug("Received token: %s", token)
            unsigned_token = token  # Using the token directly since we are not signing/unsigning
            logger.debug("Using token directly: %s", unsigned_token)
            invitation = get_object_or_404(Invitation, token=unsigned_token, accepted=False)
            logger.debug("Found invitation: %s", invitation)
        except (ValueError, Invitation.DoesNotExist) as e:
            logger.error("Error processing token: %s", e)
            if request.accepts('application/json'):
                return Response({'error': 'Invalid or expired invitation token.'}, status=status.HTTP_404_NOT_FOUND)
            else:
                messages.error(request, 'Invalid or expired invitation token.')
                return redirect('home')

        try:
            recipient_company = get_object_or_404(CompanyProfile, email=invitation.email)
            logger.debug("Found recipient company: %s", recipient_company)
        except CompanyProfile.DoesNotExist:
            logger.error("Recipient company does not exist for email: %s", invitation.email)
            if request.accepts('application/json'):
                return Response({'error': 'Recipient company profile not found.'}, status=status.HTTP_404_NOT_FOUND)
            else:
                messages.error(request, 'Recipient company profile not found.')
                return redirect('home')

        try:
            sender_company = get_object_or_404(CompanyProfile, user_profiles__user=invitation.sender)
            logger.debug("Found sender company: %s", sender_company)
        except CompanyProfile.DoesNotExist:
            logger.error("Sender company does not exist for sender: %s", invitation.sender)
            if request.accepts('application/json'):
                return Response({'error': 'Sender company profile not found.'}, status=status.HTTP_404_NOT_FOUND)
            else:
                messages.error(request, 'Sender company profile not found.')
                return redirect('home')

        if request.user.is_authenticated:
            logger.debug("User is authenticated: %s", request.user)
            user_company_profiles = request.user.userprofile.company_profiles.all()
            logger.debug("User's company profiles: %s", user_company_profiles)

            if recipient_company in user_company_profiles:
                logger.debug("Recipient company is in user's company profiles.")
                partnership, created = Partnership.objects.get_or_create(partner1=sender_company, partner2=recipient_company)
                logger.debug("Partnership created: %s, New: %s", partnership, created)

                if not created:
                    partnership.is_active = True
                    partnership.save()
                    logger.debug("Partnership reactivated: %s", partnership)

                invitation.accepted = True
                invitation.save()
                logger.debug("Invitation accepted and saved: %s", invitation)

                if request.accepts('application/json'):
                    logger.debug("Returning JSON response for accepted invitation.")
                    return Response({'message': 'Invitation accepted. You are now partners.'}, status=status.HTTP_200_OK)
                else:
                    logger.debug("Returning HTML response for accepted invitation.")
                    messages.success(request, 'Invitation accepted. You are now partners.')
                    return redirect('partners:partner_list')
            else:
                logger.debug("Recipient company is not in user's company profiles.")
                login_url = f"{reverse('account_login')}?next={reverse('invitations:accept_invitation', kwargs={'token': token})}"
                logger.debug("Redirecting to login URL: %s", login_url)
                return redirect(login_url)
        else:
            logger.debug("User is not authenticated.")
            login_url = f"{reverse('account_login')}?next={reverse('invitations:accept_invitation', kwargs={'token': token})}"
            logger.debug("Redirecting to login URL: %s", login_url)
            return redirect(login_url)
        

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
