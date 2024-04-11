
from django.urls import path, re_path
from .views import product_list, create_product, edit_product, delete_product, move_entity
from folder.views import folder_create, edit_folder
from documents.views import upload_document, delete_document, get_documents
from document_types.views import document_types_list
from . import views

#products/urls.py

app_name = 'products'

urlpatterns = [
    path('', product_list, name='product_list'),
    path('new/', create_product, name='create_product'),
    path('edit/<int:pk>/', edit_product, name='edit_product'),
    path('delete/<int:pk>/', delete_product, name='delete_product'),
    path('<int:product_id>/explorer/', views.product_explorer, name='product_explorer'),
    path('<int:product_id>/explorer/<int:folder_id>/', views.product_explorer, name='product_explorer_folder'),
    path('<int:product_id>/explorer/folder/<int:folder_id>/', views.product_explorer, name='product_explorer_with_folder'),
    # Folder control
    path('<int:product_id>/create_folder/', folder_create, name='folder_create'),
    path('<int:product_id>/explorer/edit_folder/<int:folder_id>/', edit_folder, name='edit_folder'),
    # Document management URLs within the context of a product and folder
    path('<int:product_id>/folders/<int:folder_id>/upload_document/', upload_document, name='upload_document'),
    path('<int:product_id>/folders/<int:folder_id>/documents/', get_documents, name='get_documents'),

    # New URL pattern for accessing a folder within the context of a specific product
    path('<int:product_id>/folders/<int:folder_id>/api/document_types/', document_types_list, name='document_types_list'),
    path('products/<int:product_id>/move/<str:entity_type>/<int:entity_id>/', views.move_entity, name='move_entity'),
    path('products/<int:product_id>/move/<str:entity_type>/<int:entity_id>/<int:current_folder_id>/', views.move_entity, name='move_entity'),
  

]