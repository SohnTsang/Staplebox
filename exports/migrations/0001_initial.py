# Generated by Django 5.0.2 on 2024-08-04 14:38

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('companies', '0002_initial'),
        ('documents', '0001_initial'),
        ('folder', '0001_initial'),
        ('partners', '0001_initial'),
        ('products', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Export',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('reference_number', models.CharField(blank=True, max_length=100, null=True, unique=True, verbose_name='Reference Number')),
                ('label', models.CharField(blank=True, max_length=255, null=True, verbose_name='Label')),
                ('export_date', models.DateField(verbose_name='Export Date')),
                ('completed', models.BooleanField(default=False)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_exports', to=settings.AUTH_USER_MODEL)),
                ('created_by_company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='company_exports', to='companies.companyprofile')),
                ('documents', models.ManyToManyField(blank=True, related_name='exports', to='documents.document')),
                ('folder', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='exports', to='folder.folder')),
                ('partner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exports', to='partners.partnership')),
                ('products', models.ManyToManyField(blank=True, related_name='exports', to='products.product')),
            ],
        ),
    ]
