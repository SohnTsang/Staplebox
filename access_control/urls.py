from django.urls import path
from . import views
from .views import ManageAccessView, access_control_modal, get_all_partners

app_name = 'access_control'

urlpatterns = [
    # Other URL patterns...
    path('manage_access/<str:product_uuid>/', ManageAccessView.as_view(), name='manage_access'),
    path('grant_access/<str:product_uuid>/', access_control_modal, name='grant_access'),

    path('fetch_access_details/<str:product_uuid>/<str:partner_uuid>/', views.fetch_partner_access_details, name='fetch_access_details'),
    path('remove_access/<str:product_uuid>/<str:partner_uuid>/', views.remove_access, name='remove_access'),
    path('remove_specific_access/<str:product_uuid>/<str:entity_type>/<str:entity_uuid>/', views.remove_specific_access, name='remove_specific_access'),
    
    path('get_partners_without_access/<str:product_uuid>/<str:item_uuid>/<str:item_type>/', views.get_partners_without_access, name='get_partners_without_access'),
    path('get_all_partners/', get_all_partners, name='get_all_partners'),
    path('get_partners_with_access_json/<str:item_uuid>/<str:item_type>/', views.get_partners_with_access_json, name='get_partners_with_access_json'),
]