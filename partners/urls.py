from django.urls import path
from .views import delete_partner, PartnerListView, PartnerCompanyProfileView

app_name = 'partners'  # Namespace for this urls.py

urlpatterns = [
    path('', PartnerListView.as_view(), name='partner_list'),
    path('delete/<str:partner_uuid>/', delete_partner, name='delete_partner'),
    path('<str:partner_uuid>/profile/', PartnerCompanyProfileView.as_view(), name='partner_company_profile'),
]