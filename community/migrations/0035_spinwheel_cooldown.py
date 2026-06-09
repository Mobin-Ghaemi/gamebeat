from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('community', '0034_spin_wheel_system'),
    ]

    operations = [
        # اضافه کردن فیلد cooldown_hours
        migrations.AddField(
            model_name='spinwheel',
            name='cooldown_hours',
            field=models.PositiveIntegerField(
                default=24,
                verbose_name='فاصله زمانی بین چرخش‌ها (ساعت)',
                help_text='۰ = بدون محدودیت زمانی | ۲۴ = روزانه | ۱۶۸ = هفتگی | ۷۲۰ = ماهانه',
            ),
        ),
        # مقدار cost_zarban پیش‌فرض را به ۰ تغییر می‌دهیم
        migrations.AlterField(
            model_name='spinwheel',
            name='cost_zarban',
            field=models.PositiveIntegerField(
                default=0,
                verbose_name='هزینه چرخش (ضربان، ۰ = رایگان)',
            ),
        ),
        # حذف daily_free_spins
        migrations.RemoveField(
            model_name='spinwheel',
            name='daily_free_spins',
        ),
    ]
