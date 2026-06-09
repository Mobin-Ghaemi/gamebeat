from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('community', '0024_add_location_to_gamerprofile'),
    ]

    operations = [
        migrations.AddField(
            model_name='gamerprofile',
            name='show_on_map',
            field=models.BooleanField(default=True, verbose_name='نمایش دقیق روی نقشه'),
        ),
    ]
