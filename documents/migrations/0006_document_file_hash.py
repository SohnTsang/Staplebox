# Generated by Django 5.0.2 on 2024-03-14 13:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0005_documentversion_original_filename'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='file_hash',
            field=models.CharField(blank=True, editable=False, max_length=64),
        ),
    ]
