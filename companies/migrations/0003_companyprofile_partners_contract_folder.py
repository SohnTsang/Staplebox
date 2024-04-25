# Generated by Django 5.0.2 on 2024-04-25 09:33

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0002_remove_companyprofile_company_size'),
        ('folder', '0006_folder_original_parent'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='partners_contract_folder',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='folder.folder'),
        ),
    ]
