# Generated by Django 5.0.2 on 2024-03-16 03:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0007_documentversion_file_hash'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='comments',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='documentversion',
            name='comments',
            field=models.TextField(blank=True, null=True),
        ),
    ]
