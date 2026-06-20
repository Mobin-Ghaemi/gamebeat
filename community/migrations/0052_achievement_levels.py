from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('community', '0051_add_achievement_definition'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ۱. اضافه کردن level به AchievementDefinition
        migrations.AddField(
            model_name='achievementdefinition',
            name='level',
            field=models.PositiveSmallIntegerField(default=1, verbose_name='سطح'),
        ),
        # ۲. حذف unique از ach_type در AchievementDefinition
        migrations.AlterField(
            model_name='achievementdefinition',
            name='ach_type',
            field=models.CharField(max_length=50, verbose_name='کد یکتا'),
        ),
        # ۳. unique_together روی (ach_type, level)
        migrations.AlterUniqueTogether(
            name='achievementdefinition',
            unique_together={('ach_type', 'level')},
        ),
        # ۴. ترتیب نمایش
        migrations.AlterModelOptions(
            name='achievementdefinition',
            options={
                'ordering': ['order', 'ach_type', 'level'],
                'verbose_name': 'تعریف دستاورد',
                'verbose_name_plural': 'تعاریف دستاوردها',
            },
        ),
        # ۵. اضافه کردن level به Achievement
        migrations.AddField(
            model_name='achievement',
            name='level',
            field=models.PositiveSmallIntegerField(default=1, verbose_name='سطح'),
        ),
        # ۶. unique_together روی (user, achievement_type, level)
        migrations.AlterUniqueTogether(
            name='achievement',
            unique_together={('user', 'achievement_type', 'level')},
        ),
    ]
