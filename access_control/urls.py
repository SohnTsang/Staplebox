from django.urls import path
from . import views
from documents.views import download_document

app_name = 'access_control'

urlpatterns = [
    # Other URL patterns...
    path('manage_access/<int:product_id>/', views.manage_access, name='manage_access'),
    #path('api/grant_access/', views.grant_access, name='grant_access'),
    #path('api/remove_access/<int:access_id>/', views.remove_access, name='remove_access'),
    path('view-access/', views.view_access, name='view_access'),
    path('fetch_access_details/<int:product_id>/<int:partner_id>/', views.fetch_partner_access_details, name='fetch_access_details'),
    path('remove_access/<int:product_id>/<int:partner_id>/', views.remove_access, name='remove_access'),
    path(
        'remove_specific_access/<int:product_id>/<str:entity_type>/<int:entity_id>/',
        views.remove_specific_access,
        name='remove_specific_access'
    ),

    path('get_partners_with_access_json/<int:item_id>/<str:item_type>/', views.get_partners_with_access_json, name='get_partners_with_access_json'),
    path('grant_access/<int:product_id>/', views.access_control_modal, name='grant_access'),

]