# Generated by Django 5.0.3 on 2024-04-16 06:25

import django.db.models.deletion
import django_jalali.db.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0005_alter_post_created'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='body',
            field=models.TextField(verbose_name='توضیحات'),
        ),
        migrations.AlterField(
            model_name='post',
            name='created',
            field=django_jalali.db.models.jDateTimeField(auto_now=True, verbose_name='تاریخ ایجاد'),
        ),
        migrations.AlterField(
            model_name='post',
            name='slug',
            field=models.SlugField(verbose_name='ایدی پست(اسلاگ)'),
        ),
        migrations.AlterField(
            model_name='post',
            name='updated',
            field=django_jalali.db.models.jDateTimeField(auto_now=True, verbose_name=' تاریخ اخرین ویرایش'),
        ),
        migrations.AlterField(
            model_name='post',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='کاربر'),
        ),
    ]
