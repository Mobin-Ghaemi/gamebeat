from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Game',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='نام بازی')),
                ('cover', models.ImageField(blank=True, null=True, upload_to='games/covers/', verbose_name='کاور')),
                ('genre', models.CharField(blank=True, choices=[('action', 'اکشن'), ('rpg', 'نقش‌آفرینی (RPG)'), ('sports', 'ورزشی'), ('fps', 'تیراندازی اول شخص (FPS)'), ('strategy', 'استراتژی'), ('adventure', 'ماجرایی'), ('puzzle', 'پازل'), ('horror', 'ترسناک'), ('racing', 'مسابقه‌ای'), ('fighting', 'مبارزه‌ای'), ('simulation', 'شبیه‌سازی'), ('moba', 'MOBA'), ('battle_royale', 'بتل رویال'), ('other', 'سایر')], max_length=50, verbose_name='ژانر')),
                ('platforms', models.JSONField(default=list, verbose_name='پلتفرم‌ها')),
                ('developer', models.CharField(blank=True, max_length=200, verbose_name='سازنده')),
                ('publisher', models.CharField(blank=True, max_length=200, verbose_name='ناشر')),
                ('release_year', models.IntegerField(blank=True, null=True, verbose_name='سال انتشار')),
                ('description', models.TextField(blank=True, verbose_name='توضیحات')),
                ('is_featured', models.BooleanField(default=False, verbose_name='ویژه')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'بازی',
                'verbose_name_plural': 'بازی‌ها',
                'ordering': ['name'],
            },
        ),
    ]
