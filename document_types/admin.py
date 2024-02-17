from django.contrib import admin
from .models import DocumentType

# Register your models here.
@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ('type_name', 'description', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('type_name', 'description')