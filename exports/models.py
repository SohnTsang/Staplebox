from django.db import models
from django.contrib.auth.models import User
from products.models import Product
from documents.models import Document
from partners.models import Partnership
from folder.models import Folder

class Export(models.Model):
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_exports')
    reference_number = models.CharField(max_length=100, unique=True, null=True, blank=True, verbose_name="Reference Number")
    label = models.CharField(max_length=255, blank=True, null=True, verbose_name="Label")
    export_date = models.DateField(null=True, blank=True, verbose_name="Export Date")

    def __str__(self):
        label_display = f" - {self.label}" if self.label else ""
        return f"{self.reference_number}{label_display} by {self.created_by.username}" if self.reference_number else f"Pending export by {self.created_by.username}"


class PartnerExport(models.Model):
    partner = models.ForeignKey(Partnership, on_delete=models.CASCADE, related_name='partner_exports')
    export = models.ForeignKey(Export, on_delete=models.CASCADE, related_name='partner_exports')
    export_date = models.DateField(verbose_name="Export Date", null=True, blank=True)
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='partner_export_folders')

    class Meta:
        unique_together = ('partner', 'export')
        
    def __str__(self):
        return f"{self.partner} export on {self.export_date.strftime('%Y-%m-%d')}"

    def save(self, *args, **kwargs):
        if not self.folder_id:
            self.folder = Folder.objects.create(name=f"Folder for {self.partner} on {self.export_date}")
        super().save(*args, **kwargs)

class ExportDocument(models.Model):
    partner_export = models.ForeignKey(PartnerExport, on_delete=models.CASCADE, related_name='export_documents')
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='document_exports')
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='folder_exports')

    def __str__(self):
        return f"Document {self.document.original_filename} for partner export on {self.partner_export.export_date.strftime('%Y-%m-%d')}"

class ExportProduct(models.Model):
    partner_export = models.ForeignKey(PartnerExport, on_delete=models.CASCADE, related_name='export_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_exports')

    def __str__(self):
        return f"{self.product.product_name} for export on {self.partner_export.export_date.strftime('%Y-%m-%d')}"

class StagedPartner(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='staged_partners')
    partner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='staging_user')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'partner')

    def __str__(self):
        return f"{self.user.username} staged {self.partner.username}"