# document_types/urls.py (or wherever you manage your URLs)

from django.urls import path
from .views import document_types_list

urlpatterns = [
    path('api/document_types/', document_types_list, name='document_types_list'),
]
