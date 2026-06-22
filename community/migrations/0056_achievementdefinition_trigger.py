from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('community', '0055_gamingaccount_is_public'),
    ]

    operations = [
        migrations.AddField(
            model_name='achievementdefinition',
            name='trigger',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'دستی (manual)'),
                    ('followers', 'تعداد فالوور'),
                    ('posts', 'تعداد پست'),
                    ('comments', 'تعداد کامنت'),
                    ('reactions_received', 'تعداد واکنش دریافتی'),
                ],
                default='',
                max_length=20,
                verbose_name='تریگر خودکار',
                help_text='اگه انتخاب کنی، وقتی عدد target رسید خودکار باز میشه',
            ),
        ),
    ]
