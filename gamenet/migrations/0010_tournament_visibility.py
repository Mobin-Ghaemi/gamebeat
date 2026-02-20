from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gamenet', '0009_add_ps4_ps5_controller_prices'),
    ]

    operations = [
        migrations.AddField(
            model_name='tournament',
            name='visibility',
            field=models.CharField(
                choices=[('public', 'پابلیک'), ('private', 'خصوصی')],
                default='public',
                max_length=20,
                verbose_name='نوع دسترسی',
            ),
        ),
    ]
