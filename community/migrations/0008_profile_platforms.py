from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('community', '0007_backlog_favorite'),
    ]
    operations = [
        migrations.AddField(
            model_name='gamerprofile',
            name='platforms',
            field=models.JSONField(blank=True, default=list, verbose_name='پلتفرم‌ها'),
        ),
    ]
