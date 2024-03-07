# Generated by Django 5.0.2 on 2024-03-06 15:17

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('users', '0002_remove_userprofile_role'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanyProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('role', models.CharField(blank=True, choices=[('trading', 'Trading'), ('wholesaler', 'Wholesaler'), ('retailer', 'Retailer'), ('food service', 'Food Service'), ('manufacturer', 'Manufacturer'), ('logistics', 'Logistics'), ('financial services', 'Financial services'), ('insurance', 'Insurance'), ('government agency', 'Government Agency'), ('other', 'Other')], max_length=20, null=True)),
                ('address', models.TextField()),
                ('phone_number', models.CharField(max_length=20)),
                ('email', models.EmailField(max_length=254)),
                ('company_size', models.CharField(max_length=50)),
                ('website', models.URLField(blank=True, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user_profile', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='users.userprofile')),
            ],
        ),
    ]