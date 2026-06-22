from django.db import migrations, models


def mark_existing_onboarded(apps, schema_editor):
    GamerProfile = apps.get_model('community', 'GamerProfile')
    GamerProfile.objects.all().update(has_onboarded=True)


class Migration(migrations.Migration):

    dependencies = [
        ('community', '0056_achievementdefinition_trigger'),
    ]

    operations = [
        migrations.AddField(
            model_name='gamerprofile',
            name='has_onboarded',
            field=models.BooleanField(default=False, verbose_name='انجام آنبوردینگ اولیه'),
        ),
        migrations.RunPython(mark_existing_onboarded, migrations.RunPython.noop),
    ]
