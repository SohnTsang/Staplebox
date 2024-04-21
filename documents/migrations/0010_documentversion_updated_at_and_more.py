# Generated by Django 5.0.2 on 2024-04-13 17:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0009_alter_document_original_filename'),
    ]

    operations = [
        migrations.AddField(
            model_name='documentversion',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterUniqueTogether(
            name='documentversion',
            unique_together={('document', 'version')},
        ),
    ]