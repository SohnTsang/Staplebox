from django.urls import path
from .views import partner_list_view, delete_partner, partner_company_profile
app_name = 'partners'  # Namespace for this urls.py

urlpatterns = [
    path('partners/', partner_list_view, name='partner_list'),
    path('delete/<int:partner_id>/', delete_partner, name='delete_partnercd'),
    path('partner/<int:partner_id>/profile/', partner_company_profile, name='partner_company_profile'),

]