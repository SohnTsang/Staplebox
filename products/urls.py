from django.urls import path
from .views import product_list, create_product, edit_product, delete_product
from folder.views import folder_create, folder_explorer
from documents.views import upload_document, delete_document
from . import views


urlpatterns = [
    path('', product_list, name='product_list'),
    path('new/', create_product, name='create_product'),
    path('edit/<int:pk>/', edit_product, name='edit_product'),
    path('delete/<int:pk>/', delete_product, name='delete_product'),
    path('<int:product_id>/explorer/', views.product_explorer, name='product_explorer'),
    path('<int:product_id>/explorer/create_folder/', folder_create, name='folder_create'),
    path('<int:product_id>/explorer/folder/<int:folder_id>/', folder_explorer, name='folder_explorer'),

    # Document management URLs within the context of a product and folder
    path('<int:product_id>/folders/<int:folder_id>/upload_document/', upload_document, name='upload_document'),
    # New URL pattern for accessing a folder within the context of a specific product
]