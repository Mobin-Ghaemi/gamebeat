from django.db import models

GENRE_CHOICES = [
    ('action', 'اکشن'), ('rpg', 'نقش‌آفرینی (RPG)'), ('sports', 'ورزشی'),
    ('fps', 'تیراندازی اول شخص (FPS)'), ('strategy', 'استراتژی'),
    ('adventure', 'ماجرایی'), ('puzzle', 'پازل'), ('horror', 'ترسناک'),
    ('racing', 'مسابقه‌ای'), ('fighting', 'مبارزه‌ای'), ('simulation', 'شبیه‌سازی'),
    ('moba', 'MOBA'), ('battle_royale', 'بتل رویال'), ('other', 'سایر'),
]

PLATFORM_CHOICES = [
    ('pc', 'PC'), ('ps4', 'PS4'), ('ps5', 'PS5'), ('xbox', 'Xbox'),
    ('switch', 'Nintendo Switch'), ('mobile', 'موبایل'), ('multi', 'چند پلتفرم'),
]


class Game(models.Model):
    name = models.CharField(max_length=200, verbose_name='نام بازی')
    cover = models.ImageField(upload_to='games/covers/', blank=True, null=True, verbose_name='کاور')
    genre = models.CharField(max_length=50, choices=GENRE_CHOICES, blank=True, verbose_name='ژانر')
    platforms = models.JSONField(default=list, verbose_name='پلتفرم‌ها')
    developer = models.CharField(max_length=200, blank=True, verbose_name='سازنده')
    publisher = models.CharField(max_length=200, blank=True, verbose_name='ناشر')
    release_year = models.IntegerField(null=True, blank=True, verbose_name='سال انتشار')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    is_featured = models.BooleanField(default=False, verbose_name='ویژه')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'بازی'
        verbose_name_plural = 'بازی‌ها'

    def __str__(self):
        return self.name

    def get_platform_labels(self):
        labels = dict(PLATFORM_CHOICES)
        return [labels.get(p, p) for p in self.platforms]
