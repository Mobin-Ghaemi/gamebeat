from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('community', '0006_backlog_reactions'),
    ]

    operations = [
        migrations.AddField(
            model_name='gamebacklog',
            name='is_favorite',
            field=models.BooleanField(default=False, verbose_name='مورد علاقه'),
        ),
    ]
