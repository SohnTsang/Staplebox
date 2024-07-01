from django.urls import path
from .views import delete_partner, PartnerListView, PartnerCompanyProfileView
app_name = 'partners'  # Namespace for this urls.py

urlpatterns = [
    path('', PartnerListView.as_view(), name='partner_list'),
    path('delete/<int:partner_id>/', delete_partner, name='delete_partnercd'),
    path('<int:partner_id>/profile/', PartnerCompanyProfileView.as_view(), name='partner_company_profile'),
]