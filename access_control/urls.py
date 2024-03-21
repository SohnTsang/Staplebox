from django.urls import path
from . import views
from documents.views import download_document



app_name = 'access_control'

urlpatterns = [
    # Other URL patterns...
    path('manage_access/<int:product_id>/', views.manage_access, name='manage_access'),
    #path('api/grant_access/', views.grant_access, name='grant_access'),
    path('api/get_access_details/<int:product_id>/', views.get_access_details, name='get_access_details'),
    #path('api/remove_access/<int:access_id>/', views.remove_access, name='remove_access'),
    path('view-access/', views.view_access, name='view_access'),

]