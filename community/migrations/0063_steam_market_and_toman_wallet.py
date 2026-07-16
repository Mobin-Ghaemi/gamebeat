from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('community', '0062_report'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TomanWallet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('balance', models.PositiveBigIntegerField(default=0, verbose_name='موجودی (تومان)')),
                ('locked_balance', models.PositiveBigIntegerField(default=0, verbose_name='موجودی مسدود (تومان)')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='toman_wallet', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'کیف پول تومانی',
                'verbose_name_plural': 'کیف پول‌های تومانی',
            },
        ),
        migrations.CreateModel(
            name='SteamMarketListing',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('app_id', models.PositiveIntegerField(default=730)),
                ('context_id', models.CharField(default='2', max_length=20)),
                ('asset_id', models.CharField(max_length=80)),
                ('class_id', models.CharField(blank=True, max_length=80)),
                ('instance_id', models.CharField(blank=True, max_length=80)),
                ('market_hash_name', models.CharField(max_length=255)),
                ('item_name', models.CharField(max_length=255)),
                ('icon_url', models.URLField(blank=True, max_length=600)),
                ('exterior', models.CharField(blank=True, max_length=80)),
                ('rarity', models.CharField(blank=True, max_length=80)),
                ('steam_price_usd', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('price_toman', models.PositiveBigIntegerField()),
                ('status', models.CharField(choices=[('active', 'فعال'), ('reserved', 'رزرو شده'), ('sold', 'فروخته شده'), ('cancelled', 'لغو شده')], db_index=True, default='active', max_length=12)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('sold_at', models.DateTimeField(blank=True, null=True)),
                ('buyer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='steam_purchases', to=settings.AUTH_USER_MODEL)),
                ('seller', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='steam_listings', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'آگهی بازار استیم',
                'verbose_name_plural': 'آگهی‌های بازار استیم',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TomanWalletTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transaction_type', models.CharField(choices=[('deposit', 'واریز'), ('purchase', 'خرید آیتم'), ('sale', 'فروش آیتم'), ('refund', 'بازگشت وجه'), ('adjustment', 'اصلاح دستی')], max_length=16)),
                ('amount', models.BigIntegerField(help_text='مبلغ مثبت برای افزایش و منفی برای کاهش موجودی')),
                ('balance_after', models.PositiveBigIntegerField()),
                ('reference', models.CharField(blank=True, db_index=True, max_length=80)),
                ('description', models.CharField(blank=True, max_length=240)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('wallet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='community.tomanwallet')),
            ],
            options={
                'verbose_name': 'تراکنش تومانی',
                'verbose_name_plural': 'تراکنش‌های تومانی',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='steammarketlisting',
            constraint=models.UniqueConstraint(condition=models.Q(('status__in', ['active', 'reserved'])), fields=('seller', 'app_id', 'context_id', 'asset_id'), name='unique_open_steam_asset_listing'),
        ),
    ]
