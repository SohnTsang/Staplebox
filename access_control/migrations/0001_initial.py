# Generated by Django 5.0.2 on 2024-03-05 14:27

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('documents', '0001_initial'),
        ('folder', '0001_initial'),
        ('products', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AccessPermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('document', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='documents.document')),
                ('folder', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='folder.folder')),
                ('partner1', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='granted_permissions', to=settings.AUTH_USER_MODEL)),
                ('partner2', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='received_permissions', to=settings.AUTH_USER_MODEL)),
                ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='products.product')),
            ],
            options={
                'verbose_name_plural': 'Access Permissions',
                'unique_together': {('partner1', 'partner2', 'product', 'folder', 'document')},
            },
        ),
    ]
