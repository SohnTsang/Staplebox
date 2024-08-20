from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from .forms import PasswordResetRequestForm
from django.contrib.auth.forms import PasswordResetForm
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.contrib.auth.views import PasswordResetCompleteView
from .forms import CustomLoginForm, SignupForm, UpdateEmailForm, UpdatePasswordForm
from allauth.account.utils import send_email_confirmation
from rest_framework import generics, permissions
from .serializers import UserProfileSerializer
from rest_framework.response import Response
from rest_framework import status
from django.utils.timezone import localtime
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from .models import UserActivity
from django.shortcuts import get_object_or_404
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from django.utils.http import urlsafe_base64_decode
from urllib.parse import quote
from urllib.parse import unquote
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from six import text_type
from django.views.generic import ListView
from django.utils.timezone import make_aware

import logging

logger = logging.getLogger(__name__)

def home(request):
    return render(request, 'home.html')


class CustomTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return text_type(user.pk) + text_type(timestamp)

custom_token_generator = CustomTokenGenerator()

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user.userprofile

    def get(self, request, *args, **kwargs):
        user_profile = self.get_object()
        serializer = self.get_serializer(user_profile)
        
        created_at_formatted = localtime(user_profile.created_at).strftime('%Y-%m-%d %H:%M')
        updated_at_formatted = localtime(user_profile.updated_at).strftime('%Y-%m-%d %H:%M')
        recent_activities = request.user.activities.all().order_by('-timestamp')[:6]
        
        context = {
            'user_profile': serializer.data,
            'created_at_formatted': created_at_formatted,
            'updated_at_formatted': updated_at_formatted,
            'email_form': UpdateEmailForm(instance=request.user),
            'password_form': UpdatePasswordForm(user=request.user),
            'recent_activities': recent_activities,
        }
        return render(request, 'user_profile.html', context)

    def put(self, request, *args, **kwargs):
        logger.info("Received PUT request for updating user profile.")
        
        user_profile = self.get_object()
        serializer = self.get_serializer(user_profile, data=request.data, partial=True)

        original_email = request.user.email
        email_form = UpdateEmailForm(request.data, instance=request.user)
        password_form = UpdatePasswordForm(user=request.user, data=request.data)

        if serializer.is_valid():
            logger.info("Profile serializer is valid.")
        else:
            logger.error("Profile serializer errors: %s", serializer.errors)

        if 'email' in request.data and email_form.is_valid():
            new_email = email_form.cleaned_data['email']
            if new_email != original_email:
                logger.info("New email is different from the original email, proceeding with email verification.")
                
                token = custom_token_generator.make_token(request.user)
                uid = urlsafe_base64_encode(force_bytes(request.user.pk))
                domain = get_current_site(request).domain
                verification_link = reverse('users:verify_email', kwargs={
                    'uidb64': uid,
                    'token': token,
                    'new_email': quote(new_email)
                })
                verification_url = f"http://{domain}{verification_link}"

                subject = 'Email Verification'
                message = render_to_string('account/email/email_update_verification.html', {
                    'user': request.user,
                    'verification_url': verification_url,
                })

                send_mail(subject, message, 'no-reply@example.com', [new_email])

                UserActivity.objects.create(user=request.user, action="Requested email change to " + new_email, activity_type='EMAIL_CHANGE')
                return Response({'success': True, 'message': 'A verification email has been sent. Please verify your new email address.'}, status=status.HTTP_200_OK)

        if 'old_password' in request.data:
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # Prevents user from being logged out
                UserActivity.objects.create(user=request.user, action="Updated password", activity_type='PASSWORD_CHANGE')
                return Response({'success': True, 'message': 'Password updated successfully.'}, status=status.HTTP_200_OK)
            else:
                logger.error("Password form errors: %s", password_form.errors)

        logger.error("Validation failed; returning errors.")
        errors = {**serializer.errors, **email_form.errors, **password_form.errors}
        return Response({'success': False, 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)


@login_required
def verify_email(request, uidb64, token, new_email):
    try:
        logger.info(f"Received UID: {uidb64} and Token: {token}")
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = get_object_or_404(User, pk=uid)
        logger.info(f"Decoded UID: {uid} and found User: {user.email}")

        logger.info(f"User state before token check: last_login={user.last_login}, password={user.password}")

    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        logger.error("User not found during verification.")
        user = None

    if user is not None and custom_token_generator.check_token(user, token):
        decoded_email = unquote(new_email)
        logger.info(f"Decoded email for verification: {decoded_email}")

        logger.info(f"User email before update: {user.email}")

        user.email = decoded_email
        user.save()

        logger.info(f"User email after update: {user.email}")

        UserActivity.objects.create(user=user, action=f"Verified new email address: {decoded_email}", activity_type='EMAIL_CHANGE')
        logger.info(f"User activity logged for email verification: {decoded_email}")

        # Set success message using Django's messages framework
        messages.success(request, 'Your email has been updated successfully.')
    else:
        logger.error("The verification link is invalid or has expired.")
        logger.info(f"Token that failed: {token} for user: {user.email if user else 'None'}")

        # Set error message using Django's messages framework
        messages.error(request, 'The verification link is invalid or has expired.')

    return redirect('users:user_profile')
    


class ActivityLogView(ListView):
    model = UserActivity
    template_name = 'activity_log.html'
    context_object_name = 'activities'
    paginate_by = 14  # Load 12 activities at a time

    def get_queryset(self):
        queryset = UserActivity.objects.filter(user=self.request.user).order_by('-timestamp')

        # Filter by date range
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        if start_date:
            start_date = make_aware(datetime.strptime(start_date, '%Y-%m-%d'))
            queryset = queryset.filter(timestamp__gte=start_date)
        
        if end_date:
            # Set the time to the end of the day (23:59:59) to include the whole day
            end_date = make_aware(datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1))
            queryset = queryset.filter(timestamp__lte=end_date)

        # Filter by activity type
        activity_type = self.request.GET.get('activity_type')
        if activity_type:
            queryset = queryset.filter(activity_type=activity_type)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ACTIVITY_TYPE_CHOICES'] = UserActivity.ACTIVITY_TYPE_CHOICES  # Pass the choices to the template
        return context
    

def login_signup_view(request):
    login_form = CustomLoginForm()
    signup_form = SignupForm()

    if request.user.is_authenticated:
        logger.info("User is already authenticated. Redirecting to home.")
        return redirect('home')

    # Determine the default form to show based on the request path
    default_form = 'signup' if request.path == '/accounts/signup/' else 'login'

    if request.method == "POST":
        if 'action' in request.POST and request.POST['action'] == 'login':
            logger.debug("Login form submitted.")
            login_form = CustomLoginForm(request.POST)
            if login_form.is_valid():
                login_form.login(request)
                logger.info(f"User {request.user.email} logged in successfully.")
                return redirect('home')
            else:
                messages.error(request, 'Invalid email or password.', extra_tags='invalid_user')
                logger.warning("Invalid login attempt.")
            signup_form = SignupForm()  # Reinitialize to clear previous data
            default_form = 'login'
        elif 'action' in request.POST and request.POST['action'] == 'signup':
            logger.debug("Signup form submitted.")
            signup_form = SignupForm(request.POST)
            if signup_form.is_valid():
                user = signup_form.save(request)
                user.backend = 'django.contrib.auth.backends.ModelBackend'
                send_email_confirmation(request, user, signup=True)
                logger.info(f"New user {user.email} signed up successfully.")
                return redirect('account_email_verification_sent')
            else:
                logger.warning("Signup form validation failed.")
            login_form = CustomLoginForm()  # Reinitialize to clear previous data
            default_form = 'signup'
    else:
        # Use the default form determined by the URL path
        logger.debug("GET request received. Showing default form.")
        login_form = CustomLoginForm()
        signup_form = SignupForm()

    context = {
        'login_form': login_form,
        'signup_form': signup_form,
        'show_form': default_form,  # Use the variable to control which form to show
    }
    return render(request, 'account/login_signup.html', context)

    

def password_reset_request(request):
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            username_or_email = form.cleaned_data['username_or_email']
            users = User.objects.filter(username=username_or_email) | User.objects.filter(email=username_or_email)
            if users.exists():
                user = users.first()
                form = PasswordResetForm({'email': user.email})
                token = default_token_generator.make_token(user)
                uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
                print(token)
                print(uidb64)
                context = {
                    'uidb64': uidb64,
                    'token': token,
                    'email': user.email,
                    'domain': request.get_host(),
                    'site_name': 'Staplebox',
                    'protocol': 'https' if request.is_secure() else 'http',
                    'user': user,  # Pass user to the template
                }
                if form.is_valid():
                    request.POST = request.POST.copy()
                    request.POST['email'] = user.email
                    '''
                    form.save(
                        request=request,
                        use_https=request.is_secure(),
                        email_template_name='account/email/password_reset_email.html',  # Adjust if necessary
                        subject_template_name='account/email/password_reset_subject.txt',
                        from_email=None,
                        html_email_template_name='account/email/password_reset_email.html',
                        # If you have an HTML version
                        extra_email_context=None
                    )
                    '''
                    email_subject = 'Password Reset Requested'
                    email_body = render_to_string('account/email/password_reset_email.html', context)
                    send_mail(
                        email_subject,
                        email_body,
                        'no-reply@staplebox.com',
                        [user.email],
                        fail_silently=False,
                    )
                    info_message = 'If an account exists with the email you entered, you will receive a password reset email shortly.'
                    messages.info(request, info_message)
                    return redirect(reverse_lazy('users:password_reset_request'))

            else:
                messages.error(request, 'No user found with that username or email.')
    else:
        form = PasswordResetRequestForm()
    return render(request, 'account/password_reset.html', {'form': form})


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    def get(self, request, *args, **kwargs):
        messages.success(request, 'Your password has been successfully reset. You can now log in with the new password.')
        return redirect('account_login')