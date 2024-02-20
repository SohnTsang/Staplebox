from django.urls import path
from .views import accept_invitation, send_invitation, invitation_list, delete_invitation

app_name = 'invitations'  # Namespace for this urls.py

urlpatterns = [
    path('accept/<uuid:token>/', accept_invitation, name='accept_invitation'),
    path('send/', send_invitation, name='send_invitation'),
    path('invitation-list/', invitation_list, name='invitation_list'),
    path('delete/<int:invitation_id>/', delete_invitation, name='delete_invitation'),
]