# Generated by Django 5.0.2 on 2024-02-21 13:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='partnership',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]
