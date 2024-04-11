from django.urls import path
from .views import folder_create, delete_folder, edit_folder
from products.views import product_explorer

app_name = 'folder'

urlpatterns = [
    path('<int:product_id>/explorer/', product_explorer, name='product_explorer'),
    path('<int:product_id>/explorer/create_folder/', folder_create, name='folder_create'),  # For top-level folders
    path('<int:product_id>/explorer/create_folder/<int:parent_folder_id>/', folder_create, name='subfolder_create'),  # For subfolders
    path('delete/<int:folder_id>/', delete_folder, name='delete_folder'),
    path('<int:product_id>/explorer/<int:folder_id>/edit_folder/', edit_folder, name='edit_folder'),

]