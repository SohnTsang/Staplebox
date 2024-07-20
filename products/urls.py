
from django.urls import path, re_path
from .views import move_entity
from folder.views import folder_create, edit_folder
from documents.views import get_documents, DocumentUploadView
from document_types.views import document_types_list
from . import views
from access_control.views import access_control_modal
from .views import FolderContentView, ProductListView, CreateProductView, ProductExplorerView, ListProductsAPIView, DeleteProductView, EditProductView
#products/urls.py

app_name = 'products'

urlpatterns = [
    path('', ProductListView.as_view(), name='product_list'),
    #path('new/', create_product, name='create_product'),
    path('create/', CreateProductView.as_view(), name='create_product'),

    path('edit/<int:pk>/', EditProductView.as_view(), name='edit_product'),
    path('delete/<int:pk>/', DeleteProductView.as_view(), name='delete_product'),

    path('api/products/', ListProductsAPIView.as_view(), name='api_list_products'),

    #path('<int:product_id>/explorer/', views.product_explorer, name='product_explorer'),
    #path('<int:product_id>/explorer/<int:folder_id>/', views.product_explorer, name='product_explorer_folder'),
    path('<int:product_id>/explorer/', ProductExplorerView.as_view(), name='product_explorer'),
    path('<int:product_id>/explorer/<int:folder_id>/', ProductExplorerView.as_view(), name='product_explorer_folder'),
    
    path('<int:product_id>/explorer/bin/', views.product_explorer_bin, name='product_explorer_bin'),
    path('<int:product_id>/explorer/folder/<int:folder_id>/', views.product_explorer, name='product_explorer_with_folder'),
    # Folder control
    path('<int:product_id>/create_folder/', folder_create, name='folder_create'),
    path('<int:product_id>/explorer/edit_folder/<int:folder_id>/', edit_folder, name='edit_folder'),
    # Document management URLs within the context of a product and folder
    path('<int:product_id>/folders/<int:folder_id>/upload_document/', DocumentUploadView.as_view(), name='upload_document'),
    path('<int:product_id>/folders/<int:folder_id>/documents/', get_documents, name='get_documents'),

    # New URL pattern for accessing a folder within the context of a specific product
    path('<int:product_id>/folders/<int:folder_id>/api/document_types/', document_types_list, name='document_types_list'),

    # Move entity
    #path('<int:product_id>/explorer/folder/<int:folder_id>/content/', views.folder_content, name='folder_content'),
    path('<int:product_id>/explorer/folder/<int:folder_id>/content/', FolderContentView.as_view(), name='folder_content'),


    #path('<int:product_id>/move/<str:entity_type>/<int:entity_id>/', views.move_entity, name='move_entity'),
    #path('<int:product_id>/move/<str:entity_type>/<int:entity_id>/<int:current_folder_id>/', views.move_entity, name='move_entity'),
    #path('<int:product_id>/move_entities/', views.move_entities, name='move_entities'),  # Make sure this line is correct

    path('<int:product_id>/move/<str:entity_type>/<int:entity_id>/', views.MoveEntitiesView.as_view(), name='move_entity'),
    path('<int:product_id>/move/<str:entity_type>/<int:entity_id>/<int:current_folder_id>/', views.MoveEntitiesView.as_view(), name='move_entity'),
    path('<int:product_id>/move_entities/', views.MoveEntitiesView.as_view(), name='move_entities'),

    # Access Control


]