from django.shortcuts import render, redirect, get_object_or_404
from allauth.account.views import LoginView
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
from .forms import CustomLoginForm, SignupForm
from allauth.account.utils import send_email_confirmation
import logging

logger = logging.getLogger(__name__)

def home(request):
    return render(request, 'home.html')


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