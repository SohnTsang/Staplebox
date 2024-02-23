from django.db import models
from products.models import Product

class Folder(models.Model):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfolders')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='folders')
    is_root = models.BooleanField(default=False)

    def get_ancestors(self, include_self=False):
        ancestors = []
        current = self if include_self else self.parent
        while current is not None:
            ancestors.insert(0, current)
            current = current.parent
        return ancestors

    def save(self, *args, **kwargs):
        if self.is_root:
            # If this folder is being set as root, unset any other root folders for the same product
            Folder.objects.filter(product=self.product, is_root=True).exclude(id=self.id).update(is_root=False)
        super().save(*args, **kwargs)