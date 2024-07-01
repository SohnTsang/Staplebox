from django.urls import path
from . import views
from .views import (
    ExportListView,
    ExportDetailView,
    CreateExportView,
    EditExportView,
    AddProductsToExportView,
    UploadDocumentView,
    DeleteExport,
    DownloadDocumentView,
    DeleteDocumentsView,
    RemoveProductsFromExportView,
    ExportDetailAPIView,
    CompleteExportView,  # Add this import
    CompletedExportListView  # Add this import
)

app_name = 'exports'

urlpatterns = [
    #export
    path('', ExportListView.as_view(), name='export_list'),
    path('<int:export_id>/', ExportDetailView.as_view(), name='export_detail'),
    path('<int:pk>/api/', ExportDetailAPIView.as_view(), name='export_api_detail'),

    path('create/', CreateExportView.as_view(), name='create_export'),
    path('<int:pk>/edit/', EditExportView.as_view(), name='edit_export'),

    path('<int:export_id>/complete/', CompleteExportView.as_view(), name='complete_export'),
    path('completed/', CompletedExportListView.as_view(), name='completed_export_list'),

    path('list_partners/', views.list_partners, name='list_partners'),

    path('<int:export_id>/add_products/', AddProductsToExportView.as_view(), name='add_products_to_export'),
    path('<int:export_id>/upload/', UploadDocumentView.as_view(), name='upload_document'),

    #download
    path('download/', DownloadDocumentView.as_view(), name='download_document'),
    path('download/<int:document_id>/', DownloadDocumentView.as_view(), name='download_document'),

    #delete
    path('delete/', DeleteExport.as_view(), name='delete_exports'),  # Modified to handle deletes generally
    path('<int:export_id>/delete-documents/', DeleteDocumentsView.as_view(), name='delete_documents'),
    path('<int:export_id>/remove_products/', RemoveProductsFromExportView.as_view(), name='remove_products_from_export'),
]