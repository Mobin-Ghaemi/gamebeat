from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('community', '0054_expand_city_choices'),
    ]

    operations = [
        migrations.AddField(
            model_name='gamingaccount',
            name='is_public',
            field=models.BooleanField(default=True, verbose_name='قابل مشاهده برای دیگران'),
        ),
    ]
