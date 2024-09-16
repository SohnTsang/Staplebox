from django.urls import path
from . import views
from .views import EditComment, UpdateDocument, UploadDocumentPartnerView, DocumentUploadView, DeleteDocumentView, DeletePartnerDocumentView, DownloadHistoryView



app_name = 'documents'

urlpatterns = [
    path('products/<str:product_uuid>/folders/<str:folder_uuid>/upload_document/', DocumentUploadView.as_view(), name='upload_document'),
    path('folders/<str:folder_uuid>/upload_document_partner/', UploadDocumentPartnerView.as_view(), name='upload_document_partner'),

    path('delete_documents/', DeleteDocumentView.as_view(), name='delete_documents'),
    path('delete_partner_document/<str:document_uuid>/', DeletePartnerDocumentView.as_view(), name='delete_partner_document'),

    path('products/<str:product_uuid>/folders/<str:folder_uuid>/documents/', views.get_documents, name='get_documents'),
    path('document/<str:document_uuid>/versions/', views.document_versions, name='document_versions'),
    path('download/<str:document_uuid>/<str:version_id>/', views.download_document, name='download_document_version'),
    path('download/<str:document_uuid>/', views.download_document, name='download_document'),
    path('<str:document_uuid>/download-history/', DownloadHistoryView.as_view(), name='download_history'),

    path('document/<str:document_uuid>/comments/', views.comment_versions, name='comment_versions'),
    path('document/edit/<str:document_uuid>/', views.edit_document, name='edit_document'),
    path('document/ajax/<str:document_uuid>/', views.ajax_get_document_details, name='ajax_get_document_details'),
    path('document/ajax/versions/<str:document_uuid>/', views.ajax_document_versions, name='ajax_document_versions'),

    path('move_to_bin_document/<str:document_uuid>/', views.move_to_bin_document, name='move_to_bin_document'),
    path('restore_document/<str:document_uuid>/', views.restore_document, name='restore_document'),

    path('document/ajax/update/<str:document_uuid>/', views.ajax_update_document, name='ajax_update_document'),
    path('document/update/<str:document_uuid>/', UpdateDocument.as_view(), name='update_document'),

    path('document/ajax/comments/<str:document_uuid>/', views.ajax_comments_versions, name='ajax_comments_versions'),

    path('edit_comment/<int:version_number>/', EditComment.as_view(), name='edit_comment_with_version'),
    path('document/<str:document_uuid>/edit_comment/version/<int:version_number>/', EditComment.as_view(), name='edit_comment'),
]