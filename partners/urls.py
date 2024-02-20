from django.urls import path
from .views import partner_list_view, delete_partner

app_name = 'partners'  # Namespace for this urls.py

urlpatterns = [
    path('partners/', partner_list_view, name='partner_list'),
    path('delete/<int:partner_id>/', delete_partner, name='delete_partner'),

]