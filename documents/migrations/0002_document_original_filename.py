# Generated by Django 5.0.2 on 2024-03-14 02:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='original_filename',
            field=models.CharField(default='hi', editable=False, max_length=255),
            preserve_default=False,
        ),
    ]
