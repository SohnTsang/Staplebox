# Generated by Django 5.0.2 on 2024-03-18 15:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0008_document_comments_documentversion_comments'),
    ]

    operations = [
        migrations.AlterField(
            model_name='document',
            name='original_filename',
            field=models.CharField(max_length=255),
        ),
    ]
