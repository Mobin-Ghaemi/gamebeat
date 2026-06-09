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
    genres = models.JSONField(default=list, verbose_name='ژانرها')
    platforms = models.JSONField(default=list, verbose_name='پلتفرم‌ها')
    developer = models.CharField(max_length=200, blank=True, verbose_name='سازنده')
    publisher = models.CharField(max_length=200, blank=True, verbose_name='ناشر')
    release_year = models.IntegerField(null=True, blank=True, verbose_name='سال انتشار')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    is_featured  = models.BooleanField(default=False, verbose_name='ویژه')
    is_active    = models.BooleanField(default=True,  verbose_name='فعال')
    is_online       = models.BooleanField(default=False, verbose_name='آنلاین/چندنفره')
    is_crack_online = models.BooleanField(default=False, verbose_name='کرک آنلاین')
    steam_price  = models.CharField(max_length=50, blank=True, verbose_name='قیمت استیم')
    steam_url    = models.URLField(blank=True, verbose_name='لینک استیم')
    metacritic   = models.IntegerField(null=True, blank=True, verbose_name='امتیاز متاکریتیک')
    screenshots  = models.JSONField(default=list, blank=True, verbose_name='اسکرین‌شات‌ها')
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'بازی'
        verbose_name_plural = 'بازی‌ها'

    def __str__(self):
        return self.name

    def get_platform_labels(self):
        labels = dict(PLATFORM_CHOICES)
        return [labels.get(p, p) for p in self.platforms]

    def get_genres_display(self):
        labels = dict(GENRE_CHOICES)
        return [labels.get(g, g) for g in (self.genres or [])]

    def get_primary_genre_display(self):
        labels = dict(GENRE_CHOICES)
        return labels.get(self.genres[0], self.genres[0]) if self.genres else ''
