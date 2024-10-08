# Generated by Django 5.0.2 on 2024-08-04 14:38

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('companies', '0001_initial'),
        ('folder', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Partnership',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('partner1', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='partnership_as_partner1', to='companies.companyprofile')),
                ('partner2', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='partnership_as_partner2', to='companies.companyprofile')),
                ('shared_folder', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='partnerships', to='folder.folder')),
            ],
            options={
                'unique_together': {('partner1', 'partner2')},
            },
        ),
    ]
