from django.urls import path
from .views import company_profile_view, edit_company_profile
from documents.views import upload_document_partner

app_name = 'companies'

urlpatterns = [
    path('profile/', company_profile_view, name='company_profile_view'),
    path('edit_profile/', edit_company_profile, name='edit_company_profile'),
    path('folders/<int:folder_id>/upload_document_partner/', upload_document_partner, name='upload_document_partner'),

]