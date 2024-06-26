# Generated by Django 5.0.2 on 2024-04-25 13:24

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('document_types', '0001_initial'),
        ('documents', '0012_document_bin_expires_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='document',
            name='document_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='document_types.documenttype'),
        ),
    ]
