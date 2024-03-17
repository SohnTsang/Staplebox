from django.urls import path
from . import views


app_name = 'documents'

urlpatterns = [
    path('products/<int:product_id>/folders/<int:folder_id>/upload_document/', views.upload_document, name='upload_document'),
    path('delete/<int:document_id>/', views.delete_document, name='delete_document'),
    path('products/<int:product_id>/folders/<int:folder_id>/documents/', views.get_documents, name='get_documents'),
    path('document/<int:document_id>/versions/', views.document_versions, name='document_versions'),
    path('document/<int:document_id>/<int:version_id>/', views.download_document, name='download_document'),
    path('document/<int:document_id>/', views.download_document, name='download_document'),
    path('document/update/<int:document_id>/', views.update_document, name='update_document'),
    path('edit_comment/', views.edit_comment, name='edit_comment'),  # For editing the original document comment
    path('edit_comment/<int:version_id>/', views.edit_comment, name='edit_comment'),
    path('document/<int:document_id>/comments/', views.comment_versions, name='comment_versions'),
    path('document/<int:document_id>/edit/', views.edit_document, name='edit_document'),

]