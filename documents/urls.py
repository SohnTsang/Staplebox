from django.urls import path
from . import views


app_name = 'documents'

urlpatterns = [
    path('products/<int:product_id>/folders/<int:folder_id>/upload_document/', views.upload_document, name='upload_document'),
    path('folders/<int:folder_id>/upload_document_partner/', views.upload_document_partner, name='upload_document_partner'),


    path('delete/<int:document_id>/', views.delete_document, name='delete_document'),
    path('products/<int:product_id>/folders/<int:folder_id>/documents/', views.get_documents, name='get_documents'),
    path('document/<int:document_id>/versions/', views.document_versions, name='document_versions'),
    path('document/<int:document_id>/<int:version_id>/', views.download_document, name='download_document'),
    path('document/<int:document_id>/', views.download_document, name='download_document'),
    path('document/update/<int:document_id>/', views.update_document, name='update_document'),
    path('edit_comment/', views.edit_comment, name='edit_comment'),  # For editing the original document comment
    path('edit_comment/<int:version_id>/', views.edit_comment, name='edit_comment'),
    path('document/<int:document_id>/comments/', views.comment_versions, name='comment_versions'),
    path('document/edit/<int:document_id>/', views.edit_document, name='edit_document'),
    path('document/ajax/<int:document_id>/', views.ajax_get_document_details, name='ajax_get_document_details'),
    path('document/ajax/versions/<int:document_id>/', views.ajax_document_versions, name='ajax_document_versions'),
    path('document/ajax/update/<int:document_id>/', views.ajax_update_document, name='ajax_update_document'),  # AJAX endpoint for updating a document
    
    path('move_to_bin_document/<int:document_id>/', views.move_to_bin_document, name='move_to_bin_document'),
    path('restore_document/<int:document_id>/', views.restore_document, name='restore_document'),


    path('document/ajax/comments/<int:document_id>/', views.ajax_comments_versions, name='ajax_comments_versions'),
    path('document/<int:document_id>/edit_comment/version/<int:version_number>/', views.edit_comment, name='edit_comment'),

]