# Generated by Django 5.0.2 on 2024-08-16 15:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0003_companyprofile_facebook_companyprofile_linkedin_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='profile_image',
            field=models.ImageField(blank=True, null=True, upload_to='company_profiles/'),
        ),
    ]
