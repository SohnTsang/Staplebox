# Generated by Django 5.0.2 on 2024-04-25 12:01

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('folder', '0006_folder_original_parent'),
        ('products', '0002_product_product_code_alter_product_unique_together'),
    ]

    operations = [
        migrations.AlterField(
            model_name='folder',
            name='product',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='folders', to='products.product'),
        ),
    ]
