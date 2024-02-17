from django.db import models
from products.models import Product

class Folder(models.Model):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfolders')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='folder')

    def get_ancestors(self):
        ancestors = []
        current = self.parent
        while current is not None:
            ancestors.insert(0, current)
            current = current.parent
        return ancestors