from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('community', '0027_lfg_join_system'),
    ]

    operations = [
        migrations.AddField(
            model_name='groupchat',
            name='expires_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='انقضا'),
        ),
        migrations.AddField(
            model_name='groupchat',
            name='lfg_post',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='party_group',
                to='community.lfgpost',
                verbose_name='پست LFG',
            ),
        ),
        migrations.AddField(
            model_name='groupchat',
            name='is_temp',
            field=models.BooleanField(default=False, verbose_name='گروه موقت'),
        ),
    ]
