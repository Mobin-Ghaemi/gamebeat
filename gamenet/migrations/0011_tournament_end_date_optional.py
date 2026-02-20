from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gamenet', '0010_tournament_visibility'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tournament',
            name='end_date',
            field=models.DateTimeField(blank=True, null=True, verbose_name='تاریخ پایان'),
        ),
    ]
