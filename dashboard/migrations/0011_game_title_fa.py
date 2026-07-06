from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0010_game_name_fa'),
    ]

    operations = [
        migrations.AddField(
            model_name='game',
            name='title_fa',
            field=models.CharField(
                blank=True,
                help_text='نام فارسی/رایج اصلی برای نمایش در صفحه و سئو. مثال: ولورانت',
                max_length=200,
                verbose_name='نام فارسی اصلی',
            ),
        ),
    ]
