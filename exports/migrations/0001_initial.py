# Generated by Django 5.0.2 on 2024-05-10 14:04

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('documents', '0013_alter_document_document_type'),
        ('folder', '0007_alter_folder_product'),
        ('partners', '0001_initial'),
        ('products', '0002_product_product_code_alter_product_unique_together'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Export',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('export_date', models.DateField()),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exports', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ExportPartner',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('folder', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='export_partner', to='folder.folder')),
                ('partnership', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='export_partnerships', to='partners.partnership')),
            ],
        ),
        migrations.CreateModel(
            name='ExportDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='documents.document')),
                ('export_partner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='exports.exportpartner')),
            ],
        ),
        migrations.CreateModel(
            name='ExportProduct',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('export', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='export_products', to='exports.export')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='export_products', to='products.product')),
            ],
        ),
        migrations.AddField(
            model_name='exportpartner',
            name='export_product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='export_partners', to='exports.exportproduct'),
        ),
    ]
