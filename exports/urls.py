from django.urls import path
from . import views
from documents import views as document_views

app_name = 'exports'

urlpatterns = [
    path('', views.export_list, name='export_list'),
    path('list_partners/', views.list_partners, name='list_partners'),
    path('list_products/', views.list_products, name='list_products'),

    path('get_export_dates/<int:partner_id>/', views.get_export_dates, name='get_export_dates'),
    path('get_export_documents/<int:partner_export_id>/', views.get_export_documents, name='get_export_documents'),

    path('create_with_date/', views.create_export_with_date, name='create_export_with_date'),
    path('add_partner_to_staging/', views.add_partner_to_staging, name='add_partner_to_staging'),
    path('<int:export_id>/add_product/', views.add_product_to_export, name='add_product_to_export'),
    path('upload_document/<int:partner_export_id>/', document_views.upload_document_to_partner_export, name='upload_document_to_partner_export'),
    path('delete_exports/', views.delete_exports, name='delete_exports'),
    path('delete_documents/', views.delete_documents, name='delete_documents'),
    path('delete_partners/', views.delete_partners, name='delete_partners'),
]