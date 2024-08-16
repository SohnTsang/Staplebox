from django.urls import path, re_path
from .views import SendInvitation, AcceptInvitation, DeleteInvitation

app_name = 'invitations'  # Namespace for this urls.py

urlpatterns = [
    path('accept/<uuid:token>/', AcceptInvitation.as_view(), name='accept_invitation'),
    path('send/', SendInvitation.as_view(), name='send_invitation'),
    path('delete/<int:invitation_id>/', DeleteInvitation.as_view(), name='delete_invitation'),
]