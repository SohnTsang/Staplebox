from django.urls import path
from . import views

app_name = 'exports'

urlpatterns = [
    path('', views.export_list, name='export_list'),  # The main SPA for export management
    path('list_partners/', views.list_partners, name='list_partners'),

    path('create/', views.create_export, name='create_export'),
    path('list_products/', views.list_products, name='list_products'),
    path('<int:export_id>/add_product/', views.add_product_to_export, name='add_product_to_export'),
    path('<int:export_partner_id>/upload_document/', views.upload_document_to_partner, name='upload_document_to_partner'),
    path('<int:export_id>/delete/', views.delete_export, name='delete_export'),

]
