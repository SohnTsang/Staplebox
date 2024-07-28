from django.urls import path
from .views import folder_create, DeleteFolderView
from . import views

app_name = 'folder'

urlpatterns = [
    
    path('<str:product_uuid>/explorer/create_folder/', folder_create, name='folder_create'),  # For top-level folders
    path('<str:product_uuid>/explorer/create_folder/<str:parent_folder_uuid>/', folder_create, name='subfolder_create'),  # For subfolders

    path('delete_folders/', DeleteFolderView.as_view(), name='delete_folders'),  # For multiple deletions

    path('get_folder_data/', views.get_folder_data, name='get_folder_data'),
    path('<str:product_uuid>/explorer/<str:folder_uuid>/edit_folder/', views.edit_folder, name='edit_folder'),
   

    path('ajax/<str:product_uuid>/<str:folder_uuid>/', views.ajax_get_folder_details, name='ajax_get_folder_details'),
    
    path('move_to_bin_folder/<str:folder_uuid>/', views.move_to_bin_folder, name='move_to_bin_folder'),
    path('restore_folder/<str:folder_uuid>/', views.restore_folder, name='restore_folder'),

]