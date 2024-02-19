from django.urls import path
from . import views


app_name = 'documents'

urlpatterns = [
    path('products/<int:product_id>/folders/<int:folder_id>/upload_document/', views.upload_document, name='upload_document'),
    path('delete/<int:document_id>/', views.delete_document, name='delete_document'),
    path('download/<int:document_id>/', views.download_document, name='download_document'),
    path('products/<int:product_id>/folders/<int:folder_id>/documents/', views.get_documents, name='get_documents'),

]