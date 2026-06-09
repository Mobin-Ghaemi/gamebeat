from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0005_game_is_online'),
    ]

    operations = [
        migrations.AddField(
            model_name='game',
            name='is_crack_online',
            field=models.BooleanField(default=False, verbose_name='کرک آنلاین'),
        ),
    ]
