from django.shortcuts import render, redirect
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
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView, PasswordResetCompleteView
from django.contrib.auth import views as auth_views


def home(request):
    return render(request, 'home.html')

class LoginView(LoginView):
    def get_form(self, *args, **kwargs):
        form = super().get_form(*args, **kwargs)
        # Change the label of the 'login' field to 'Email'
        form.fields['login'].label = "Email"
        return form


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