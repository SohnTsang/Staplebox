from django.urls import path
from .views import create_company_profile, CompanyProfileView, EditCompanyProfileView, LinkUserToCompanyView, ShowCompanyTokenView
from documents.views import UploadDocumentPartnerView

app_name = 'companies'

urlpatterns = [
    path('profile/', CompanyProfileView.as_view(), name='company_profile_view'),
    path('edit_profile/', EditCompanyProfileView.as_view(), name='edit_company_profile'),
    path('link-company/', LinkUserToCompanyView.as_view(), name='link_company'),  # New URL
    path('token/<str:company_uuid>/', ShowCompanyTokenView.as_view(), name='show_company_token'),

    #path('folders/<int:folder_id>/upload_document_partner/', upload_document_partner, name='upload_document_partner'),
    path('folders/<str:folder_uuid>/upload_document_partner/', UploadDocumentPartnerView.as_view(), name='upload_document_partner'),

]