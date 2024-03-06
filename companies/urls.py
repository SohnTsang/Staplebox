from django.urls import path
from .views import company_profile_view, edit_company_profile

app_name = 'companies'

urlpatterns = [
    path('profile/', company_profile_view, name='company_profile_view'),
    path('edit_profile/', edit_company_profile, name='edit_company_profile'),
]