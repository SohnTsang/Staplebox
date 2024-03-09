from django import forms
from django.core.exceptions import ValidationError
from .models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['product_code', 'product_name', 'product_description', 'product_type']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)  # Extract user from kwargs
        super(ProductForm, self).__init__(*args, **kwargs)

    def clean_product_code(self):
        product_code = self.cleaned_data.get('product_code')
        qs = Product.objects.filter(user=self.user, product_code=product_code)

        # For the edit case, exclude the current instance from the check
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise ValidationError('A product with this code already exists for you.')

        return product_code