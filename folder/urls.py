from django.urls import path
from .views import folder_create, folder_explorer, delete_folder
from products.views import product_explorer
app_name = 'folder'

urlpatterns = [
    path('<int:product_id>/explorer/', product_explorer, name='product_explorer'),
    path('<int:product_id>/explorer/create_folder/', folder_create, name='folder_create'),  # For top-level folders
    path('<int:product_id>/explorer/create_folder/<int:parent_folder_id>/', folder_create, name='subfolder_create'),  # For subfolders
    path('<int:product_id>/explorer/folder/<int:folder_id>/', folder_explorer, name='folder_explorer'),
    path('delete/<int:folder_id>/', delete_folder, name='delete_folder'),

]