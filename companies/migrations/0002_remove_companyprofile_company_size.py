# Generated by Django 5.0.2 on 2024-03-06 15:57

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='companyprofile',
            name='company_size',
        ),
    ]