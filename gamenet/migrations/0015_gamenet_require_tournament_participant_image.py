from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gamenet", "0014_participant_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamenet",
            name="require_tournament_participant_image",
            field=models.BooleanField(
                default=False,
                verbose_name="اجباری بودن تصویر شرکت‌کننده در مسابقات",
            ),
        ),
    ]

