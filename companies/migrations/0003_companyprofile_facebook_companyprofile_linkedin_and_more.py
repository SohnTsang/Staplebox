# Generated by Django 5.0.2 on 2024-08-05 13:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='facebook',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='linkedin',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='primary_contact_email',
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='primary_contact_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='twitter',
            field=models.URLField(blank=True, null=True),
        ),
    ]
