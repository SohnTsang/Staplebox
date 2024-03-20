# Generated by Django 5.0.2 on 2024-03-19 15:39

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('folder', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='folder',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='folder',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
