# Generated by Django 5.0.3 on 2024-04-07 10:20

import django_jalali.db.models
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0002_alter_post_created_alter_post_updated'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='created',
            field=django_jalali.db.models.jDateField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name='post',
            name='updated',
            field=django_jalali.db.models.jDateField(auto_now=True),
        ),
    ]