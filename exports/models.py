from django.db import models
from django.contrib.auth.models import User
from products.models import Product
from documents.models import Document
from partners.models import Partnership
from folder.models import Folder

class Export(models.Model):
    partner = models.ForeignKey(Partnership, on_delete=models.CASCADE, related_name='exports')
    export_date = models.DateField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_exports')

    def __str__(self):
        return f"{self.export_date.strftime('%Y-%m-%d')} for {self.partner}"

class ExportProduct(models.Model):
    export = models.ForeignKey(Export, on_delete=models.CASCADE, related_name='export_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_exports')

    def __str__(self):
        return f"{self.product.product_name} on {self.export.export_date.strftime('%Y-%m-%d')}"

class ExportDocument(models.Model):
    export = models.ForeignKey(Export, on_delete=models.CASCADE, related_name='export_documents')
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='document_exports')
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='folder_exports')

    def __str__(self):
        return f"Document {self.document.id} for export on {self.export.export_date.strftime('%Y-%m-%d')}"
