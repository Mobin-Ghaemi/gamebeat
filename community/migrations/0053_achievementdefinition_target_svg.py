from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('community', '0052_achievement_levels'),
    ]

    operations = [
        migrations.AddField(
            model_name='achievementdefinition',
            name='target',
            field=models.PositiveIntegerField(default=0, verbose_name='هدف عددی (مثلاً ۱۰ فالوور)'),
        ),
        migrations.AddField(
            model_name='achievementdefinition',
            name='icon_svg',
            field=models.FileField(blank=True, null=True, upload_to='achievements/icons/', verbose_name='آیکون SVG (اختیاری)'),
        ),
    ]
