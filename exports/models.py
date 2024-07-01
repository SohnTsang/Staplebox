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
    export_date = models.DateField(verbose_name="Export Date")
    partner = models.ForeignKey(Partnership, on_delete=models.CASCADE, related_name='exports')
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='exports', null=True, blank=True)
    documents = models.ManyToManyField(Document, related_name='exports', blank=True)
    products = models.ManyToManyField(Product, related_name='exports', blank=True)
    completed = models.BooleanField(default=False)  # Add this line

    def __str__(self):
        label_display = f" - {self.label}" if self.label else ""
        return f"{self.reference_number}{label_display} by {self.created_by.username}" if self.reference_number else f"Pending export by {self.created_by.username}"

    def save(self, *args, **kwargs):
        # Automatically create a folder for the export if not already set
        if not self.folder_id:
            self.folder = Folder.objects.create(name=f"Folder for {self.partner} on {self.export_date}")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Delete associated documents and the folder
        if self.folder:
            print("yes folder")
            self.folder.delete()
            print(self.folder)
        if self.documents:
            print("yes docs")
            print(self.documents.all())
            self.documents.all().delete()
        super().delete(*args, **kwargs)
