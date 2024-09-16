
from django.urls import path, re_path
from folder.views import folder_create, edit_folder
from documents.views import get_documents, DocumentUploadView
from document_types.views import document_types_list
from . import views
from access_control.views import access_control_modal
from .views import FolderContentView, ProductListView, CreateProductView, ProductExplorerView, ListProductsAPIView, DeleteProductView, EditProductView, PartnerProductExplorerView
#products/urls.py

app_name = 'products'

urlpatterns = [
    path('', ProductListView.as_view(), name='product_list'),
    path('create/', CreateProductView.as_view(), name='create_product'),
    path('edit/<str:product_uuid>/', EditProductView.as_view(), name='edit_product'),
    path('delete/<str:product_uuid>/', DeleteProductView.as_view(), name='delete_product'),
    path('api/products/', ListProductsAPIView.as_view(), name='api_list_products'),
    path('<str:product_uuid>/explorer/', ProductExplorerView.as_view(), name='product_explorer'),
    path('<str:product_uuid>/explorer/<str:folder_uuid>/', ProductExplorerView.as_view(), name='product_explorer_folder'),

    # New URL patterns for the partner-specific explorer
    path('<str:product_uuid>/partner/<str:partner_uuid>/explorer/', PartnerProductExplorerView.as_view(), name='partner_product_explorer'),
    path('<str:product_uuid>/partner/<str:partner_uuid>/explorer/<str:folder_uuid>/', PartnerProductExplorerView.as_view(), name='partner_product_explorer_folder'),

    path('<str:product_uuid>/explorer/bin/', views.product_explorer_bin, name='product_explorer_bin'),
    # Folder control
    path('<str:product_uuid>/create_folder/', folder_create, name='folder_create'),
    path('<str:product_uuid>/explorer/edit_folder/<str:folder_uuid>/', edit_folder, name='edit_folder'),
    # Document management URLs within the context of a product and folder
    path('<str:product_uuid>/folders/<str:folder_uuid>/upload_document/', DocumentUploadView.as_view(), name='upload_document'),
    path('<str:product_uuid>/folders/<str:folder_uuid>/documents/', get_documents, name='get_documents'),
    # New URL pattern for accessing a folder within the context of a specific product
    path('<str:product_uuid>/folders/<str:folder_uuid>/api/document_types/', document_types_list, name='document_types_list'),
    # Move entity
    path('<str:product_uuid>/explorer/folder/<str:folder_uuid>/content/', FolderContentView.as_view(), name='folder_content'),
    path('<str:product_uuid>/move/<str:entity_type>/<str:entity_uuid>/', views.MoveEntitiesView.as_view(), name='move_entity'),
    path('<str:product_uuid>/move/<str:entity_type>/<str:entity_uuid>/<str:current_folder_uuid>/', views.MoveEntitiesView.as_view(), name='move_entity'),
    path('<str:product_uuid>/move_entities/', views.MoveEntitiesView.as_view(), name='move_entities'),
    # Access Control
]