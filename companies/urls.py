from django.urls import path
from .views import CompanyProfileView, EditCompanyProfileView
from documents.views import UploadDocumentPartnerView

app_name = 'companies'

urlpatterns = [
    path('profile/', CompanyProfileView.as_view(), name='company_profile_view'),

    path('edit_profile/', EditCompanyProfileView.as_view(), name='edit_company_profile'),

    #path('folders/<int:folder_id>/upload_document_partner/', upload_document_partner, name='upload_document_partner'),
    path('folders/<int:folder_id>/upload_document_partner/', UploadDocumentPartnerView.as_view(), name='upload_document_partner'),

]