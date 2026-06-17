import datetime
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


PLATFORM_CHOICES = [
    ('pc', 'PC'),
    ('ps4', 'PlayStation 4'),
    ('ps5', 'PlayStation 5'),
    ('xbox', 'Xbox'),
    ('switch', 'Nintendo Switch'),
    ('mobile', 'موبایل'),
    ('multi', 'چند پلتفرم'),
]

GAMING_STYLE_CHOICES = [
    ('competitive', 'رقابتی / Competitive'),
    ('casual', 'تفریحی / Casual'),
    ('streamer', 'استریمر'),
    ('pro', 'حرفه‌ای / Pro'),
    ('collector', 'کالکتور'),
    ('rpg_lover', 'دوستدار RPG'),
]

CITY_CHOICES = [
    ('tehran', 'تهران'),
    ('mashhad', 'مشهد'),
    ('isfahan', 'اصفهان'),
    ('shiraz', 'شیراز'),
    ('tabriz', 'تبریز'),
    ('ahvaz', 'اهواز'),
    ('karaj', 'کرج'),
    ('qom', 'قم'),
    ('rasht', 'رشت'),
    ('kermanshah', 'کرمانشاه'),
    ('urmia', 'ارومیه'),
    ('zahedan', 'زاهدان'),
    ('hamadan', 'همدان'),
    ('arak', 'اراک'),
    ('yazd', 'یزد'),
    ('other', 'سایر'),
]

RANK_CHOICES = [
    ('bronze', 'برنز'),
    ('silver', 'نقره'),
    ('gold', 'طلا'),
    ('platinum', 'پلاتینیوم'),
    ('diamond', 'الماس'),
    ('master', 'مستر'),
    ('grandmaster', 'گرندمستر'),
    ('challenger', 'چلنجر'),
]


class GamerProfile(models.Model):
    NAME_DISPLAY_CHOICES = [
        ('full', 'نام و نام خانوادگی'),
        ('nickname', 'نام مستعار'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='gamer_profile', verbose_name='کاربر')
    bio = models.TextField(max_length=500, blank=True, verbose_name='درباره من')
    nickname = models.CharField(max_length=50, blank=True, verbose_name='نام مستعار')
    name_display = models.CharField(max_length=10, choices=NAME_DISPLAY_CHOICES, default='full', verbose_name='نمایش نام در پروفایل')
    avatar = models.ImageField(upload_to='community/avatars/', blank=True, null=True, verbose_name='آواتار')
    banner = models.ImageField(upload_to='community/banners/', blank=True, null=True, verbose_name='بنر پروفایل')
    city = models.CharField(max_length=20, choices=CITY_CHOICES, blank=True, verbose_name='شهر')
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES, default='pc', verbose_name='پلتفرم اصلی')
    platforms = models.JSONField(default=list, blank=True, verbose_name='پلتفرم‌ها')
    gaming_style = models.CharField(max_length=20, choices=GAMING_STYLE_CHOICES, blank=True, verbose_name='سبک بازی')
    gaming_styles = models.JSONField(default=list, blank=True, verbose_name='سبک‌های بازی')
    rank = models.CharField(max_length=15, choices=RANK_CHOICES, blank=True, verbose_name='رنک')
    favorite_games = models.TextField(blank=True, verbose_name='بازی‌های مورد علاقه')
    phone = models.CharField(max_length=20, blank=True, verbose_name='شماره تماس')
    national_id = models.CharField(max_length=10, blank=True, verbose_name='کد ملی')
    steam_id = models.CharField(max_length=100, blank=True, verbose_name='Steam ID')
    psn_id = models.CharField(max_length=100, blank=True, verbose_name='PSN ID')
    xbox_gamertag = models.CharField(max_length=100, blank=True, verbose_name='Xbox Gamertag')
    total_hours_played = models.PositiveIntegerField(default=0, verbose_name='ساعت بازی')
    is_verified = models.BooleanField(default=False, verbose_name='تأیید‌شده', help_text='بج آبی تیک — برای ادمین کلاب‌ها/استریمرهای شناخته‌شده')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── Privacy & Settings ──
    is_private        = models.BooleanField(default=False, verbose_name='پروفایل خصوصی')
    show_online       = models.BooleanField(default=True,  verbose_name='نمایش آنلاین بودن')
    show_last_seen    = models.BooleanField(default=True,  verbose_name='نمایش آخرین بازدید')
    show_email        = models.BooleanField(default=False, verbose_name='نمایش ایمیل')
    allow_dm          = models.BooleanField(default=True,  verbose_name='دریافت پیام مستقیم')
    dm_followers_only = models.BooleanField(default=False, verbose_name='پیام فقط از دنبال‌کننده‌ها')
    show_backlog      = models.BooleanField(default=True,  verbose_name='نمایش بک‌لاگ')
    show_stats        = models.BooleanField(default=True,  verbose_name='نمایش آمار')
    last_seen         = models.DateTimeField(null=True, blank=True, verbose_name='آخرین بازدید')

    # ── Location (Gamer Finder) ──
    location_lat   = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name='عرض جغرافیایی')
    location_lng   = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name='طول جغرافیایی')
    location_label = models.CharField(max_length=100, blank=True, verbose_name='شهر/محله')
    show_location  = models.BooleanField(default=False, verbose_name='نمایش موقعیت')
    show_on_map    = models.BooleanField(default=True,  verbose_name='نمایش دقیق روی نقشه')

    class Meta:
        verbose_name = 'پروفایل گیمر'
        verbose_name_plural = 'پروفایل‌های گیمران'

    def __str__(self):
        return f'@{self.user.username}'

    @property
    def display_name(self):
        """نامی که در پروفایل نمایش داده می‌شود — طبق انتخاب کاربر."""
        if self.name_display == 'nickname' and self.nickname.strip():
            return self.nickname.strip()
        full = self.user.get_full_name().strip()
        return full or self.nickname.strip() or self.user.username

    @property
    def followers_count(self):
        return Follow.objects.filter(following=self.user).count()

    @property
    def following_count(self):
        return Follow.objects.filter(follower=self.user).count()

    @property
    def posts_count(self):
        return Post.objects.filter(author=self.user).count()

    def get_favorite_games_list(self):
        if self.favorite_games:
            return [g.strip() for g in self.favorite_games.split(',') if g.strip()]
        return []

    def get_platforms_list(self):
        """Returns list of platform codes — uses new platforms field, falls back to old platform"""
        if self.platforms:
            return self.platforms
        elif self.platform:
            return [self.platform]
        return []

    def get_gaming_styles_list(self):
        """Returns list of gaming-style codes — uses new gaming_styles field, falls back to old gaming_style"""
        if self.gaming_styles:
            return self.gaming_styles
        elif self.gaming_style:
            return [self.gaming_style]
        return []

    def get_gaming_styles_display(self):
        """Returns list of human labels for the selected gaming styles"""
        labels = dict(GAMING_STYLE_CHOICES)
        return [labels.get(s, s) for s in self.get_gaming_styles_list()]

    def get_platform_display_list(self):
        """Returns list of (code, display_name, icon) tuples for all platforms"""
        icons = {
            'pc': 'bi-pc-display', 'ps4': 'bi-playstation', 'ps5': 'bi-playstation',
            'xbox': 'bi-xbox', 'switch': 'bi-nintendo-switch', 'mobile': 'bi-phone', 'multi': 'bi-controller',
        }
        labels = dict(PLATFORM_CHOICES)
        return [(p, labels.get(p, p), icons.get(p, 'bi-controller')) for p in self.get_platforms_list()]

    pinned_game_name = models.CharField(max_length=120, blank=True, verbose_name='بازی پین‌شده')

    @property
    def is_premium(self):
        return PremiumSubscription.objects.filter(
            user=self.user,
            is_active=True,
            end_date__gt=timezone.now()
        ).exists()

    @property
    def completed_games_count(self):
        return GameBacklog.objects.filter(user=self.user, status='completed').count()

    @property
    def favorite_genre(self):
        """Auto-calculate most played genre from completed games matching Game catalog"""
        from dashboard.models import Game, GENRE_CHOICES
        completed_names = GameBacklog.objects.filter(user=self.user, status='completed').values_list('game_name', flat=True)
        genre_count = {}
        for name in completed_names:
            game = Game.objects.filter(name__iexact=name).first()
            if game and game.genres:
                for g in game.genres:
                    genre_count[g] = genre_count.get(g, 0) + 1
        if not genre_count:
            return None
        top = max(genre_count, key=genre_count.get)
        labels = dict(GENRE_CHOICES)
        return labels.get(top, top)

    @property
    def platform_icon(self):
        icons = {
            'pc': 'bi-pc-display',
            'ps4': 'bi-playstation',
            'ps5': 'bi-playstation',
            'xbox': 'bi-xbox',
            'switch': 'bi-nintendo-switch',
            'mobile': 'bi-phone',
            'multi': 'bi-controller',
        }
        return icons.get(self.platform, 'bi-controller')


class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following_set', verbose_name='دنبال‌کننده')
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers_set', verbose_name='دنبال‌شونده')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')
        verbose_name = 'دنبال کردن'
        verbose_name_plural = 'دنبال کردن‌ها'
        indexes = [
            models.Index(fields=['follower']),
            models.Index(fields=['following']),
        ]

    def __str__(self):
        return f'{self.follower.username} → {self.following.username}'


class FollowRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('accepted', 'پذیرفته شده'),
        ('rejected', 'رد شده'),
    ]
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_follow_requests', verbose_name='فرستنده')
    to_user   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_follow_requests', verbose_name='گیرنده')
    status    = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('from_user', 'to_user')
        verbose_name = 'درخواست دنبال کردن'
        verbose_name_plural = 'درخواست‌های دنبال کردن'

    def __str__(self):
        return f'{self.from_user.username} → {self.to_user.username} ({self.status})'


class Hashtag(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    post_count = models.PositiveIntegerField(default=0)
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-post_count']

    def __str__(self):
        return f'#{self.name}'


class Post(models.Model):
    POST_TYPES = [
        ('text', 'متن'),
        ('achievement', 'دستاورد'),
        ('lfg', 'جستجوی تیم'),
        ('highlight', 'هایلایت'),
        ('image', 'تصویر'),
        ('link', 'لینک'),
    ]

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts', verbose_name='نویسنده')
    content = models.TextField(verbose_name='محتوا')
    image = models.ImageField(upload_to='community/posts/', blank=True, null=True, verbose_name='تصویر')
    video = models.FileField(upload_to='community/posts/videos/', blank=True, null=True, verbose_name='ویدیو')
    post_type = models.CharField(max_length=15, choices=POST_TYPES, default='text', verbose_name='نوع پست')
    game_tag = models.CharField(max_length=100, blank=True, verbose_name='تگ بازی')
    is_public = models.BooleanField(default=True, verbose_name='عمومی')
    is_approved = models.BooleanField(default=True, verbose_name='تأیید شده')
    hashtags = models.ManyToManyField('Hashtag', blank=True, related_name='posts')
    link_url = models.URLField(blank=True)
    link_title = models.CharField(max_length=300, blank=True)
    link_description = models.TextField(blank=True)
    link_image_url = models.URLField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)
    is_boosted      = models.BooleanField(default=False, verbose_name='بوست شده')
    boost_expires_at = models.DateTimeField(null=True, blank=True, verbose_name='انقضای بوست')

    class Meta:
        verbose_name = 'پست'
        verbose_name_plural = 'پست‌ها'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['author', '-created_at']),
            models.Index(fields=['is_public', '-created_at']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'{self.author.username}: {self.content[:50]}'

    @property
    def boost_active(self):
        return self.is_boosted and self.boost_expires_at and self.boost_expires_at > timezone.now()

    @property
    def likes_count(self):
        return self.likes.count()

    @property
    def comments_count(self):
        return self.comments.count()


class PostLike(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes', verbose_name='پست')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='کاربر')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')
        verbose_name = 'لایک'
        verbose_name_plural = 'لایک‌ها'


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments', verbose_name='پست')
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='نویسنده')
    content = models.TextField(max_length=500, verbose_name='محتوا')
    is_approved = models.BooleanField(default=True, verbose_name='تأیید شده')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'کامنت'
        verbose_name_plural = 'کامنت‌ها'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.author.username} on post {self.post.id}'


class LFGPost(models.Model):
    GAME_MODES = [
        ('ranked', 'رنکد'),
        ('normal', 'نرمال'),
        ('tournament', 'تورنمنت'),
        ('custom', 'کاستوم'),
        ('coop', 'Co-op'),
    ]

    SKILL_LEVELS = [
        ('beginner', 'تازه‌کار'),
        ('intermediate', 'متوسط'),
        ('advanced', 'پیشرفته'),
        ('pro', 'حرفه‌ای'),
        ('any', 'همه سطوح'),
    ]

    JOIN_TYPES = [
        ('open',    'مستقیم — هر کسی می‌تواند بپیوندد'),
        ('request', 'درخواستی — باید تأیید شود'),
    ]

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lfg_posts', verbose_name='پست‌دهنده')
    game_name = models.CharField(max_length=100, verbose_name='نام بازی')
    game_mode = models.CharField(max_length=15, choices=GAME_MODES, default='normal', verbose_name='مود بازی')
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES, verbose_name='پلتفرم')
    skill_level = models.CharField(max_length=15, choices=SKILL_LEVELS, default='any', verbose_name='سطح مهارت')
    description = models.TextField(max_length=300, blank=True, verbose_name='توضیحات')
    max_players = models.PositiveSmallIntegerField(default=4, verbose_name='حداکثر بازیکن')
    current_players = models.PositiveSmallIntegerField(default=1, verbose_name='بازیکنان فعلی')
    join_type = models.CharField(max_length=10, choices=JOIN_TYPES, default='open', verbose_name='نوع پیوستن')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'پست LFG'
        verbose_name_plural = 'پست‌های LFG'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.author.username} - {self.game_name}'

    @property
    def spots_left(self):
        return self.max_players - self.current_players


class LFGJoinRequest(models.Model):
    STATUS = [
        ('pending',  'در انتظار'),
        ('accepted', 'پذیرفته شده'),
        ('rejected', 'رد شده'),
    ]
    post       = models.ForeignKey(LFGPost, on_delete=models.CASCADE, related_name='join_requests', verbose_name='پست')
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lfg_join_requests', verbose_name='کاربر')
    status     = models.CharField(max_length=10, choices=STATUS, default='pending', verbose_name='وضعیت')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('post', 'user')]
        verbose_name = 'درخواست پیوستن LFG'
        verbose_name_plural = 'درخواست‌های پیوستن LFG'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} → {self.post}'


class Achievement(models.Model):
    ACHIEVEMENT_TYPES = [
        ('first_post', 'اولین پست'),
        ('first_follow', 'اولین فالو'),
        ('popular_post', 'پست پرلایک'),
        ('veteran', 'کهنه‌کار'),
        ('social', 'اجتماعی'),
        ('tournament_win', 'برنده تورنمنت'),
        ('custom', 'سفارشی'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='achievements', verbose_name='کاربر')
    achievement_type = models.CharField(max_length=20, choices=ACHIEVEMENT_TYPES, verbose_name='نوع دستاورد')
    title = models.CharField(max_length=100, verbose_name='عنوان')
    description = models.CharField(max_length=200, blank=True, verbose_name='توضیح')
    icon = models.CharField(max_length=50, default='bi-trophy', verbose_name='آیکون')
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'دستاورد'
        verbose_name_plural = 'دستاوردها'
        ordering = ['-earned_at']

    def __str__(self):
        return f'{self.user.username} - {self.title}'


class GamingAccount(models.Model):
    PLATFORM_CHOICES = [
        ('steam', 'Steam'),
        ('xbox', 'Xbox Live'),
        ('psn', 'PlayStation Network'),
        ('ea', 'EA / Origin'),
        ('epic', 'Epic Games'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='gaming_accounts')
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    username = models.CharField(max_length=120)
    display_name = models.CharField(max_length=120, blank=True)
    avatar_url = models.URLField(blank=True)
    profile_url = models.URLField(blank=True)
    extra_data = models.JSONField(default=dict, blank=True)
    verified = models.BooleanField(default=False)
    connected_at = models.DateTimeField(auto_now_add=True)
    last_synced = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'platform')

    def __str__(self):
        return f"{self.user.username} - {self.platform}: {self.username}"


# ═══════════════════════════════════════
#  GAME BACKLOG
# ═══════════════════════════════════════

class GameBacklog(models.Model):
    STATUS_CHOICES = [
        ('want',      'می‌خوام بازی کنم'),
        ('playing',   'دارم بازی می‌کنم'),
        ('completed', 'تموم کردم'),
        ('dropped',   'رها کردم'),
    ]

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='backlog')
    game_name  = models.CharField(max_length=120, verbose_name='نام بازی')
    status     = models.CharField(max_length=12, choices=STATUS_CHOICES, default='want')
    platform   = models.CharField(max_length=10, choices=PLATFORM_CHOICES, blank=True)
    rating     = models.PositiveSmallIntegerField(null=True, blank=True)   # 1–10, only when completed
    notes      = models.CharField(max_length=300, blank=True)
    cover_url  = models.URLField(blank=True)
    is_favorite = models.BooleanField(default=False, verbose_name='مورد علاقه')
    added_at   = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'بک‌لاگ'
        verbose_name_plural = 'بک‌لاگ‌ها'
        ordering = ['-updated_at']
        unique_together = ('user', 'game_name')
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'is_favorite']),
            models.Index(fields=['user', '-updated_at']),
        ]

    def __str__(self):
        return f'{self.user.username} – {self.game_name} [{self.status}]'


# ═══════════════════════════════════════
#  POST REACTIONS
# ═══════════════════════════════════════

class PostReaction(models.Model):
    REACTION_CHOICES = [
        ('fire',     '🔥 خفن'),
        ('dead',     '💀 GG'),
        ('tryhard',  '😤 عصبانی'),
        ('legend',   '👑 لجند'),
        ('ggez',     '😂 GG EZ'),
        ('cry',      '😢 گریه'),
        ('sob',      '😭 اشک'),
    ]

    REACTION_EMOJI = {
        'fire':    '🔥',
        'dead':    '💀',
        'tryhard': '😤',
        'legend':  '👑',
        'ggez':    '😂',
        'cry':     '😢',
        'sob':     '😭',
    }

    REACTION_LABEL = {
        'fire':    'خفن',
        'dead':    'GG',
        'tryhard': 'عصبانی',
        'legend':  'لجند',
        'ggez':    'GG EZ',
        'cry':     'گریه',
        'sob':     'اشک',
    }

    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reactions')
    post          = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reactions')
    reaction_type = models.CharField(max_length=10, choices=REACTION_CHOICES)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')
        verbose_name = 'واکنش'
        verbose_name_plural = 'واکنش‌ها'

    def __str__(self):
        return f'{self.user.username} {self.reaction_type} on post {self.post_id}'


# ═══════════════════════════════════════
#  NOTIFICATIONS
# ═══════════════════════════════════════

class Notification(models.Model):
    NOTIF_TYPES = [
        ('like',           'لایک پست'),
        ('comment',        'کامنت'),
        ('follow',         'فالو'),
        ('follow_request',  'درخواست دنبال کردن'),
        ('follow_accepted', 'پذیرش دنبال کردن'),
        ('follow_rejected', 'رد دنبال کردن'),
        ('mention',        'منشن'),
        ('admin',          'پیام ادمین'),
        ('dm',             'پیام خصوصی'),
        ('lfg_join',       'پیوستن مستقیم LFG'),
        ('lfg_req',        'درخواست LFG'),
        ('lfg_ok',         'تأیید درخواست LFG'),
        ('lfg_no',         'رد درخواست LFG'),
        ('zarban',         'ضربان'),
        ('spin',           'گردونه شانس'),
        ('profile_view',   'بازدید پروفایل'),
        ('view_digest',    'خلاصه بازدیدها'),
    ]

    recipient   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications', null=True, blank=True)
    notif_type  = models.CharField(max_length=15, choices=NOTIF_TYPES)
    post        = models.ForeignKey('Post', on_delete=models.CASCADE, null=True, blank=True)
    custom_text = models.CharField(max_length=500, blank=True, default='')
    is_read     = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'اعلان'
        verbose_name_plural = 'اعلان‌ها'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.sender} → {self.recipient} [{self.notif_type}]'

    @property
    def text(self):
        if self.custom_text:
            return self.custom_text
        if self.notif_type == 'like':
            return f'{self.sender.username} پستت رو لایک کرد'
        elif self.notif_type == 'comment':
            return f'{self.sender.username} روی پستت کامنت گذاشت'
        elif self.notif_type == 'follow':
            return f'{self.sender.username} شروع کرد به دنبال کردنت'
        elif self.notif_type == 'mention':
            return f'{self.sender.username} تو رو منشن کرد'
        elif self.notif_type == 'admin':
            return 'پیام جدید از ادمین'
        elif self.notif_type == 'dm':
            return f'{self.sender.username} برات پیام فرستاد'
        return ''

    @property
    def icon(self):
        icons = {'like': '❤️', 'comment': '💬', 'follow': '👤', 'mention': '📢', 'admin': '📣', 'dm': '💬', 'zarban': '💜', 'profile_view': '👁️'}
        return icons.get(self.notif_type, '🔔')


# ═══════════════════════════════════════
#  DIRECT MESSAGES
# ═══════════════════════════════════════

class Conversation(models.Model):
    participants = models.ManyToManyField(User, related_name='conversations')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'مکالمه'
        verbose_name_plural = 'مکالمات'
        ordering = ['-updated_at']

    def other_participant(self, user):
        return self.participants.exclude(pk=user.pk).first()

    @property
    def last_message(self):
        return self.messages.order_by('-created_at').first()


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    content      = models.TextField(max_length=2000, blank=True)
    image        = models.ImageField(upload_to='dm/images/', blank=True, null=True)
    file         = models.FileField(upload_to='dm/files/', blank=True, null=True)
    file_name    = models.CharField(max_length=255, blank=True)
    is_read      = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'پیام'
        verbose_name_plural = 'پیام‌ها'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender.username}: {self.content[:40]}'


# ═══════════════════════════════════════
#  BLOCK / PIN / MUTE
# ═══════════════════════════════════════

class Block(models.Model):
    blocker    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocking')
    blocked    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('blocker', 'blocked')
        verbose_name = 'بلاک'
        verbose_name_plural = 'بلاک‌ها'

    def __str__(self):
        return f'{self.blocker.username} blocked {self.blocked.username}'


class PinnedConversation(models.Model):
    user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pinned_convs')
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='pinned_by')
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'conversation')
        verbose_name = 'مکالمه پین‌شده'
        verbose_name_plural = 'مکالمات پین‌شده'


class MutedConversation(models.Model):
    user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='muted_convs')
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='muted_by')
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'conversation')
        verbose_name = 'مکالمه میوت‌شده'
        verbose_name_plural = 'مکالمات میوت‌شده'


# ═══════════════════════════════════════
#  ACTIVITY LOG
# ═══════════════════════════════════════

class ActivityLog(models.Model):
    ACTIVITY_TYPES = [
        ('started_playing', 'شروع به بازی کرد'),
        ('completed',       'تموم کرد'),
        ('added_to_list',   'اضافه کرد به لیستش'),
        ('dropped',         'رها کرد'),
        ('rated',           'امتیاز داد'),
    ]
    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    game_name     = models.CharField(max_length=120)
    game_id       = models.IntegerField(null=True, blank=True)
    extra         = models.JSONField(default=dict, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'فعالیت'
        verbose_name_plural = 'فعالیت‌ها'

    def __str__(self):
        return f'{self.user.username} - {self.activity_type} - {self.game_name}'


# ═══════════════════════════════════════
#  CHALLENGES
# ═══════════════════════════════════════

class Challenge(models.Model):
    CHALLENGE_TYPES = [
        ('most_completed', 'بیشترین بازی تموم‌شده'),
        ('most_added',     'بیشترین بازی اضافه‌شده'),
        ('genre_week',     'ژانر هفته'),
    ]
    title          = models.CharField(max_length=200, verbose_name='عنوان')
    description    = models.TextField(blank=True, verbose_name='توضیحات')
    challenge_type = models.CharField(max_length=20, choices=CHALLENGE_TYPES)
    genre_filter   = models.CharField(max_length=20, blank=True)
    start_date     = models.DateTimeField(verbose_name='شروع')
    end_date       = models.DateTimeField(verbose_name='پایان')
    is_active      = models.BooleanField(default=True, verbose_name='فعال')
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'چالش'
        verbose_name_plural = 'چالش‌ها'
        ordering = ['-start_date']

    def __str__(self):
        return self.title

    def get_leaderboard(self):
        from django.db.models import Count
        if self.challenge_type == 'most_completed':
            return (GameBacklog.objects
                .filter(status='completed', updated_at__gte=self.start_date, updated_at__lte=self.end_date)
                .values('user__username', 'user__gamer_profile__avatar', 'user')
                .annotate(score=Count('id'))
                .order_by('-score')[:10])
        elif self.challenge_type == 'most_added':
            return (GameBacklog.objects
                .filter(added_at__gte=self.start_date, added_at__lte=self.end_date)
                .values('user__username', 'user__gamer_profile__avatar', 'user')
                .annotate(score=Count('id'))
                .order_by('-score')[:10])
        return []


# ═══════════════════════════════════════
#  CLUBS
# ═══════════════════════════════════════

class Club(models.Model):
    name        = models.CharField(max_length=100, unique=True, verbose_name='نام گروه')
    slug        = models.SlugField(max_length=100, unique=True, allow_unicode=True)
    description = models.TextField(blank=True, verbose_name='توضیحات')
    avatar      = models.ImageField(upload_to='clubs/avatars/', blank=True, null=True, verbose_name='آواتار گروه')
    banner      = models.ImageField(upload_to='clubs/banners/', blank=True, null=True, verbose_name='بنر گروه')
    owner       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_clubs', verbose_name='مالک')
    genre_tag   = models.CharField(max_length=20, blank=True, verbose_name='ژانر')
    is_public   = models.BooleanField(default=True, verbose_name='عمومی')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'گروه'
        verbose_name_plural = 'گروه‌ها'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        return self.memberships.count()


class ClubMember(models.Model):
    ROLE_CHOICES = [('owner', 'مالک'), ('admin', 'ادمین'), ('member', 'عضو')]
    club      = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='memberships')
    user      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='club_memberships')
    role      = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('club', 'user')
        verbose_name = 'عضو گروه'
        verbose_name_plural = 'اعضای گروه'

    def __str__(self):
        return f'{self.user.username} in {self.club.name} [{self.role}]'


class ClubPost(models.Model):
    club       = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='posts')
    author     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='club_posts')
    content    = models.TextField(verbose_name='محتوا')
    image      = models.ImageField(upload_to='clubs/posts/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'پست گروه'
        verbose_name_plural = 'پست‌های گروه'

    def __str__(self):
        return f'{self.author.username} in {self.club.name}: {self.content[:40]}'


# ═══════════════════════════════════════
#  GROUP CHAT (گروه پیامی)
# ═══════════════════════════════════════

class GroupChat(models.Model):
    name        = models.CharField(max_length=100, verbose_name='نام گروه')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    icon        = models.ImageField(upload_to='groups/icons/', blank=True, null=True, verbose_name='آیکون')
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_groups')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    expires_at  = models.DateTimeField(null=True, blank=True, verbose_name='انقضا')
    lfg_post    = models.OneToOneField('LFGPost', null=True, blank=True, on_delete=models.SET_NULL, related_name='party_group', verbose_name='پست LFG')
    is_temp     = models.BooleanField(default=False, verbose_name='گروه موقت')

    class Meta:
        verbose_name = 'گروه چت'
        verbose_name_plural = 'گروه‌های چت'
        ordering = ['-updated_at']

    def __str__(self):
        return self.name

    @property
    def is_expired(self):
        from django.utils import timezone
        return bool(self.expires_at and self.expires_at < timezone.now())

    @property
    def last_message(self):
        return self.group_messages.order_by('-created_at').first()

    @property
    def member_count(self):
        return self.group_members.count()


class GroupMember(models.Model):
    ROLE_CHOICES = [('owner', 'مالک'), ('admin', 'ادمین'), ('member', 'عضو')]
    group        = models.ForeignKey(GroupChat, on_delete=models.CASCADE, related_name='group_members')
    user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_memberships')
    role         = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    joined_at    = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('group', 'user')
        verbose_name = 'عضو گروه چت'
        verbose_name_plural = 'اعضای گروه چت'

    def __str__(self):
        return f'{self.user.username} in {self.group.name} [{self.role}]'

    @property
    def is_admin(self):
        return self.role in ('owner', 'admin')


class GroupMessage(models.Model):
    group      = models.ForeignKey(GroupChat, on_delete=models.CASCADE, related_name='group_messages')
    sender     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_sent_messages')
    content    = models.TextField(max_length=2000, blank=True)
    image      = models.ImageField(upload_to='groups/images/', blank=True, null=True)
    file       = models.FileField(upload_to='groups/files/', blank=True, null=True)
    file_name  = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'پیام گروه'
        verbose_name_plural = 'پیام‌های گروه'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender.username} → {self.group.name}: {self.content[:40]}'


class PinnedGroupChat(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pinned_groups')
    group      = models.ForeignKey(GroupChat, on_delete=models.CASCADE, related_name='pinned_by_users')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'group')


class MutedGroupChat(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='muted_groups')
    group      = models.ForeignKey(GroupChat, on_delete=models.CASCADE, related_name='muted_by_users')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'group')


# ═══════════════════════════════════════
#  CHANNEL (کانال)
# ═══════════════════════════════════════

class Channel(models.Model):
    name         = models.CharField(max_length=100, verbose_name='نام کانال')
    username     = models.SlugField(max_length=50, unique=True, verbose_name='نام کاربری کانال')
    description  = models.TextField(blank=True, verbose_name='توضیحات')
    icon         = models.ImageField(upload_to='channels/icons/', blank=True, null=True, verbose_name='آیکون')
    owner        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_channels')
    is_public    = models.BooleanField(default=True, verbose_name='عمومی')
    # ── تنظیمات جدید ──
    show_author      = models.BooleanField(default=True,  verbose_name='نمایش نویسنده پست')
    require_approval = models.BooleanField(default=False, verbose_name='درخواست عضویت نیاز به تایید دارد')
    linked_group     = models.ForeignKey('GroupChat', on_delete=models.SET_NULL, null=True, blank=True, related_name='linked_channel', verbose_name='گروه متصل')
    reactions_enabled = models.BooleanField(default=True, verbose_name='ری‌اکشن فعال')
    comments_enabled  = models.BooleanField(default=False, verbose_name='کامنت فعال')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'کانال'
        verbose_name_plural = 'کانال‌ها'
        ordering = ['-updated_at']

    def __str__(self):
        return f'@{self.username}'

    @property
    def subscriber_count(self):
        return self.channel_members.count()

    @property
    def last_post(self):
        return self.channel_posts.order_by('-created_at').first()


class ChannelMember(models.Model):
    ROLE_CHOICES = [('owner', 'مالک'), ('admin', 'ادمین'), ('subscriber', 'مشترک')]
    channel      = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='channel_members')
    user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='channel_memberships')
    role         = models.CharField(max_length=12, choices=ROLE_CHOICES, default='subscriber')
    joined_at    = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('channel', 'user')
        verbose_name = 'عضو کانال'
        verbose_name_plural = 'اعضای کانال'

    def __str__(self):
        return f'{self.user.username} → @{self.channel.username} [{self.role}]'

    @property
    def can_post(self):
        return self.role in ('owner', 'admin')


class ChannelPost(models.Model):
    channel    = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='channel_posts')
    author     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='channel_authored_posts')
    content    = models.TextField(blank=True, verbose_name='محتوا')
    image      = models.ImageField(upload_to='channels/posts/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'پست کانال'
        verbose_name_plural = 'پست‌های کانال'
        ordering = ['-created_at']

    def __str__(self):
        return f'@{self.channel.username}: {self.content[:40]}'

    @property
    def reaction_count(self):
        return self.channel_reactions.count()


class ChannelJoinRequest(models.Model):
    STATUS_CHOICES = [('pending','در انتظار'),('accepted','پذیرفته'),('rejected','رد شده')]
    channel    = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='join_requests')
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='channel_join_requests')
    status     = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('channel', 'user')
        verbose_name = 'درخواست عضویت کانال'

    def __str__(self):
        return f'{self.user.username} → @{self.channel.username}'


class ChannelReaction(models.Model):
    EMOJI_CHOICES = [('🔥','fire'),('👍','like'),('❤️','heart'),('😂','lol'),('😮','wow'),('👏','clap')]
    post       = models.ForeignKey(ChannelPost, on_delete=models.CASCADE, related_name='channel_reactions')
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='channel_reactions')
    emoji      = models.CharField(max_length=5, choices=EMOJI_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')
        verbose_name = 'ری‌اکشن کانال'
        verbose_name_plural = 'ری‌اکشن‌های کانال'


class PinnedChannel(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pinned_channels')
    channel    = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='pinned_by_users')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'channel')


class MutedChannel(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='muted_channels')
    channel    = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='muted_by_users')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'channel')


# ════════════════════════════════════════════════════════
#  ردیابی زمان آنلاین کاربران
# ════════════════════════════════════════════════════════
class UserSession(models.Model):
    """
    هر بار که کاربر وارد سایت شود یک سشن ایجاد می‌شود.
    Middleware هر درخواست last_activity را به‌روز می‌کند.
    بعد از ۱۵ دقیقه بی‌فعالیت، سشن بسته و مدت آن محاسبه می‌شود.
    """
    SESSION_TIMEOUT = 15 * 60  # ۱۵ دقیقه (ثانیه)

    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='online_sessions')
    started_at    = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now_add=True)
    ended_at      = models.DateTimeField(null=True, blank=True)
    # مدت واقعی حضور (ثانیه) — از started_at تا last_activity
    duration_secs = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name        = 'سشن کاربر'
        verbose_name_plural = 'سشن‌های کاربران'
        indexes = [
            models.Index(fields=['user', 'ended_at', '-last_activity']),
        ]

    def __str__(self):
        return f'{self.user.username} — {self.started_at:%Y-%m-%d %H:%M}'

    @property
    def is_active(self):
        if self.ended_at:
            return False
        return (timezone.now() - self.last_activity).total_seconds() < self.SESSION_TIMEOUT

    def close(self):
        """بستن سشن و محاسبه مدت حضور."""
        if not self.ended_at:
            self.ended_at    = timezone.now()
            self.duration_secs = max(0, int((self.last_activity - self.started_at).total_seconds()))
            self.save(update_fields=['ended_at', 'duration_secs'])

    # حداکثر فاصله بین دو نوشتن واقعی last_activity روی DB (ثانیه)
    TOUCH_THROTTLE = 90

    @classmethod
    def get_or_create_active(cls, user):
        """
        سشن فعال موجود را برمی‌گرداند یا سشن جدید می‌سازد.
        سشن‌های قدیمی/باز‌مانده را می‌بندد.

        برای جلوگیری از SELECT/UPDATE روی هر درخواست (مخصوصاً heartbeat
        که هر ۶۰ ثانیه می‌زند)، pk سشن فعال در cache نگه داشته می‌شود و
        نوشتن واقعی last_activity حداکثر هر TOUCH_THROTTLE ثانیه انجام می‌شود.
        """
        from django.core.cache import cache
        now = timezone.now()

        cache_key = f'active_session_pk_{user.id}'
        touch_key = f'active_session_touch_{user.id}'
        cached_pk = cache.get(cache_key)

        if cached_pk:
            if not cache.get(touch_key):
                cache.set(touch_key, True, cls.TOUCH_THROTTLE)
                cls.objects.filter(pk=cached_pk, ended_at__isnull=True).update(last_activity=now)
            return None

        cutoff = now - timezone.timedelta(seconds=cls.SESSION_TIMEOUT)
        active = cls.objects.filter(
            user=user, ended_at__isnull=True, last_activity__gte=cutoff
        ).order_by('-last_activity').first()

        if active:
            cls.objects.filter(pk=active.pk).update(last_activity=now)
            cache.set(cache_key, active.pk, cls.SESSION_TIMEOUT)
            cache.set(touch_key, True, cls.TOUCH_THROTTLE)
            return active

        # بستن سشن‌های باز قدیمی
        for stale in cls.objects.filter(user=user, ended_at__isnull=True):
            stale.close()

        # سشن جدید
        new_session = cls.objects.create(user=user)
        cache.set(cache_key, new_session.pk, cls.SESSION_TIMEOUT)
        cache.set(touch_key, True, cls.TOUCH_THROTTLE)
        return new_session

    @classmethod
    def total_seconds_in_period(cls, user_ids, since=None):
        """
        مجموع ثانیه‌های آنلاین هر کاربر در بازه مشخص.
        بازگشت: dict  {user_id: total_seconds}
        """
        from django.db.models import Sum, Q
        qs = cls.objects.filter(user_id__in=user_ids, ended_at__isnull=False)
        if since:
            qs = qs.filter(started_at__gte=since)
        rows = qs.values('user_id').annotate(total=Sum('duration_secs'))
        result = {r['user_id']: r['total'] for r in rows}

        # اضافه کردن سشن فعال فعلی (هنوز بسته نشده)
        active_qs = cls.objects.filter(user_id__in=user_ids, ended_at__isnull=True)
        if since:
            active_qs = active_qs.filter(started_at__gte=since)
        now = timezone.now()
        for s in active_qs.select_related():
            secs = max(0, int((min(s.last_activity, now) - s.started_at).total_seconds()))
            result[s.user_id] = result.get(s.user_id, 0) + secs

        return result

    @classmethod
    def check_and_award_zarban(cls, user):
        """
        کل ثانیه‌های آنلاین کاربر (همه سشن‌ها) را حساب می‌کند.
        به ازای هر ساعت کامل جدید، ضربان واریز می‌کند.
        cross-session: ۵۰ دقیقه لاگ‌اوت + ۱۰ دقیقه = ۱ ساعت = ۱ جایزه
        """
        try:
            total_map = cls.total_seconds_in_period([user.id])
            total_secs = total_map.get(user.id, 0)
            total_hours = int(total_secs // 3600)

            # خواندن کیف پول
            from community.models import ZarbanWallet, ZarbanTransaction, Notification, ScoreSettings
            wallet = ZarbanWallet.get_or_create_for(user)

            new_hours = total_hours - wallet.online_zarban_hours
            if new_hours <= 0:
                return

            cfg = ScoreSettings.get()
            reward_per_hour = cfg.online_hour_score  # از تنظیمات ادمین

            total_reward = new_hours * reward_per_hour
            wallet.balance += total_reward
            wallet.online_zarban_hours = total_hours
            wallet.save(update_fields=['balance', 'online_zarban_hours', 'updated_at'])

            ZarbanTransaction.objects.create(
                wallet=wallet,
                amount=total_reward,
                tx_type=ZarbanTransaction.TX_CREDIT,
                reason=f'جایزه {new_hours} ساعت حضور آنلاین',
            )

            # نوتیف به کاربر
            admin_user = User.objects.filter(username='admin').first()
            Notification.objects.create(
                recipient=user,
                sender=admin_user,
                notif_type='zarban',
                custom_text=f'💜 {total_reward} ضربان بابت {new_hours} ساعت حضور آنلاین به شما تعلق گرفت!',
            )
        except Exception:
            pass  # هیچ‌وقت نباید سایت را خراب کند


# ════════════════════════════════════════════════════════
#  تنظیمات امتیاز  —  Singleton (همیشه یک رکورد با pk=1)
# ════════════════════════════════════════════════════════
class ScoreSettings(models.Model):
    """
    مدل singleton برای تنظیم ضریب ضربان لیدربورد.
    هرگز بیشتر از یک ردیف نباید وجود داشته باشد.
    """
    post_score        = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='ضربان هر پست',
        help_text='هر پست چند ضربان داشته باشد؟',
    )
    comment_score     = models.PositiveSmallIntegerField(
        default=2,
        verbose_name='ضربان هر کامنت',
        help_text='هر کامنت چند ضربان داشته باشد؟',
    )
    active_day_score  = models.PositiveSmallIntegerField(
        default=5,
        verbose_name='ضربان هر روز فعال',
        help_text='هر روزی که کاربر پست یا کامنت داشته باشد چند ضربان دریافت می‌کند؟',
    )
    online_hour_score = models.PositiveSmallIntegerField(
        default=2,
        verbose_name='ضربان هر ساعت آنلاین',
        help_text='به ازای هر ساعت حضور در سایت چند ضربان؟',
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین ویرایش')

    class Meta:
        verbose_name        = 'تنظیمات ضربان'
        verbose_name_plural = 'تنظیمات ضربان'

    def __str__(self):
        return f'پست×{self.post_score} | کامنت×{self.comment_score} | روز فعال×{self.active_day_score} | ساعت×{self.online_hour_score}'

    @classmethod
    def get(cls):
        """Singleton accessor — همیشه همان رکورد pk=1 را برمی‌گرداند."""
        from django.core.cache import cache
        obj = cache.get('score_settings')
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set('score_settings', obj, timeout=300)
        return obj

    def save(self, *args, **kwargs):
        # همیشه pk=1 تا singleton بماند
        self.pk = 1
        super().save(*args, **kwargs)
        # کش را پاک کن
        from django.core.cache import cache
        cache.delete('score_settings')


# ════════════════════════════════════════════════════════
#  💜 سیستم ارز ضربان
# ════════════════════════════════════════════════════════

class ZarbanWallet(models.Model):
    """کیف پول ضربان هر کاربر — یک رکورد به ازای هر User"""
    user    = models.OneToOneField(User, on_delete=models.CASCADE, related_name='zarban_wallet')
    balance = models.PositiveIntegerField(default=0, verbose_name='موجودی ضربان')
    # تعداد ساعت‌هایی که تا الان بابت آنلاین بودن ضربان گرفته
    online_zarban_hours = models.PositiveIntegerField(default=0, verbose_name='ساعت‌های جایزه‌داده‌شده')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'کیف پول ضربان'
        verbose_name_plural = 'کیف‌پول‌های ضربان'

    def __str__(self):
        return f'{self.user.username}: {self.balance} 💜'

    @classmethod
    def get_or_create_for(cls, user):
        wallet, _ = cls.objects.get_or_create(user=user)
        return wallet


class ZarbanTransaction(models.Model):
    TX_CREDIT = 'credit'
    TX_DEBIT  = 'debit'
    TX_TYPES  = [
        (TX_CREDIT, 'افزایش'),
        (TX_DEBIT,  'کاهش'),
    ]

    wallet     = models.ForeignKey(ZarbanWallet, on_delete=models.CASCADE, related_name='transactions')
    amount     = models.PositiveIntegerField(verbose_name='مقدار')
    tx_type    = models.CharField(max_length=10, choices=TX_TYPES, verbose_name='نوع')
    reason     = models.CharField(max_length=400, blank=True, verbose_name='دلیل')
    admin      = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='zarban_given', verbose_name='ادمین')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'تراکنش ضربان'
        verbose_name_plural = 'تراکنش‌های ضربان'
        ordering = ['-created_at']

    def __str__(self):
        sign = '+' if self.tx_type == self.TX_CREDIT else '-'
        return f'{self.wallet.user.username} {sign}{self.amount} 💜'

    def delete(self, *args, **kwargs):
        # حذف ممنوع است
        pass

    @classmethod
    def get(cls):
        """دریافت تنظیمات با کش ۵ دقیقه‌ای."""
        from django.core.cache import cache
        obj = cache.get('score_settings')
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set('score_settings', obj, 300)
        return obj


# ════════════════════════════════════════════════════════
#  اسنپ‌شات لیدربورد  —  ذخیره امتیاز قبل از هر ریست
# ════════════════════════════════════════════════════════
class LeaderboardSnapshot(models.Model):
    """
    امتیاز و رتبه هر کاربر در هر دوره بسته‌شده ذخیره می‌شود.
    با دستور: python manage.py snapshot_leaderboard --period weekly
    """
    PERIOD_CHOICES = [
        ('weekly',  'هفتگی'),
        ('monthly', 'ماهانه'),
        ('yearly',  'سالانه'),
    ]

    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lb_snapshots')
    period_type   = models.CharField(max_length=10, choices=PERIOD_CHOICES, verbose_name='نوع دوره')
    period_key    = models.CharField(max_length=20, verbose_name='کلید دوره',
                                     help_text='مثال: 2026-W22 | 2026-06 | 2026')
    rank          = models.PositiveSmallIntegerField(default=0, verbose_name='رتبه')
    score         = models.PositiveIntegerField(default=0, verbose_name='امتیاز')
    post_count    = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    active_days   = models.PositiveIntegerField(default=0)
    online_secs   = models.PositiveIntegerField(default=0)
    snapshotted_at = models.DateTimeField(auto_now_add=True, verbose_name='زمان ثبت')

    class Meta:
        unique_together = [('user', 'period_type', 'period_key')]
        ordering = ['period_type', 'period_key', 'rank']
        verbose_name        = 'اسنپ‌شات لیدربورد'
        verbose_name_plural = 'اسنپ‌شات‌های لیدربورد'

    def __str__(self):
        return f'{self.user.username} | {self.period_type} {self.period_key} | رتبه {self.rank}'


# ══════════════════════════════════════════════════════════
#  🎰  سیستم گردونه شانس
# ══════════════════════════════════════════════════════════

class SpinWheel(models.Model):
    name            = models.CharField(max_length=100, verbose_name='نام گردونه')
    description     = models.TextField(blank=True, default='', verbose_name='توضیحات')
    cooldown_hours  = models.PositiveIntegerField(
        default=24,
        verbose_name='فاصله زمانی بین چرخش‌ها (ساعت)',
        help_text='۰ = بدون محدودیت زمانی | ۲۴ = روزانه | ۱۶۸ = هفتگی | ۷۲۰ = ماهانه',
    )
    cost_zarban     = models.PositiveIntegerField(default=0, verbose_name='هزینه چرخش (ضربان، ۰ = رایگان)')
    is_active       = models.BooleanField(default=True, verbose_name='فعال')
    order           = models.PositiveSmallIntegerField(default=0, verbose_name='ترتیب نمایش')
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = 'گردونه شانس'
        verbose_name_plural = 'گردونه‌های شانس'

    def __str__(self):
        return self.name

    @property
    def total_probability(self):
        return sum(i.probability for i in self.items.filter(is_active=True))


class SpinWheelItem(models.Model):
    REWARD_ZARBAN  = 'zarban'
    REWARD_XP      = 'xp'
    REWARD_SPIN    = 'spin'
    REWARD_NOTHING = 'nothing'
    REWARD_TYPES = [
        (REWARD_ZARBAN,  'ضربان 💜'),
        (REWARD_XP,      'XP ⚡'),
        (REWARD_SPIN,    'چرخش رایگان 🎰'),
        (REWARD_NOTHING, 'بدشانسی 💀'),
    ]

    wheel         = models.ForeignKey(SpinWheel, on_delete=models.CASCADE, related_name='items')
    name          = models.CharField(max_length=100, verbose_name='نام آیتم')
    probability   = models.FloatField(default=10.0, verbose_name='درصد شانس')
    reward_type   = models.CharField(max_length=10, choices=REWARD_TYPES, default=REWARD_NOTHING, verbose_name='نوع جایزه')
    reward_amount = models.PositiveIntegerField(default=0, verbose_name='مقدار جایزه')
    color         = models.CharField(max_length=7, default='#6d28d9', verbose_name='رنگ خانه')
    emoji         = models.CharField(max_length=300, default='🎁', verbose_name='ایموجی')
    is_active     = models.BooleanField(default=True, verbose_name='فعال')
    order         = models.PositiveSmallIntegerField(default=0, verbose_name='ترتیب')

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'آیتم گردونه'
        verbose_name_plural = 'آیتم‌های گردونه'

    def __str__(self):
        return f'{self.wheel.name} — {self.name} ({self.probability}%)'


class SpinRecord(models.Model):
    user    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='spin_records', verbose_name='کاربر')
    wheel   = models.ForeignKey(SpinWheel, on_delete=models.CASCADE, related_name='spin_records', verbose_name='گردونه')
    item    = models.ForeignKey(SpinWheelItem, on_delete=models.SET_NULL, null=True, related_name='spin_records', verbose_name='آیتم برنده')
    is_free = models.BooleanField(default=True, verbose_name='رایگان بود؟')
    cost    = models.PositiveIntegerField(default=0, verbose_name='هزینه پرداختی')
    spun_at = models.DateTimeField(auto_now_add=True, verbose_name='زمان چرخش')

    class Meta:
        ordering = ['-spun_at']
        verbose_name = 'رکورد چرخش'
        verbose_name_plural = 'رکوردهای چرخش'

    def __str__(self):
        return f'{self.user.username} — {self.wheel.name} — {self.spun_at:%Y/%m/%d}'


# ═══════════════════════════════════════
#  GAME REVIEWS
# ═══════════════════════════════════════

class GameReview(models.Model):
    game_id   = models.IntegerField(verbose_name='شناسه بازی', db_index=True)
    game_name = models.CharField(max_length=120, verbose_name='نام بازی')
    user      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='game_reviews', verbose_name='کاربر')
    rating    = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='امتیاز (1-10)')
    body      = models.TextField(max_length=1000, verbose_name='متن نظر')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'نظر بازی'
        verbose_name_plural = 'نظرات بازی‌ها'
        ordering = ['-created_at']
        unique_together = ('user', 'game_id')

    def __str__(self):
        return f'{self.user.username} — {self.game_name}'


# ═══════════════════════════════════════
#  PREMIUM
# ═══════════════════════════════════════

class PremiumPlan(models.Model):
    DURATION_CHOICES = [
        ('1_month',  '۱ ماهه'),
        ('6_months', '۶ ماهه'),
        ('1_year',   '۱ ساله'),
    ]
    name        = models.CharField(max_length=100, verbose_name='نام پلن')
    duration    = models.CharField(max_length=20, choices=DURATION_CHOICES, verbose_name='مدت')
    price       = models.PositiveIntegerField(verbose_name='قیمت (تومان)')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    features    = models.TextField(blank=True, verbose_name='امکانات (هر خط یک امکان)')
    is_active   = models.BooleanField(default=True, verbose_name='فعال')
    created_at  = models.DateTimeField(auto_now_add=True)

    DURATION_DAYS = {'1_month': 30, '6_months': 180, '1_year': 365}

    class Meta:
        verbose_name = 'پلن پریمیوم'
        verbose_name_plural = 'پلن‌های پریمیوم'
        ordering = ['price']

    def __str__(self):
        return f'{self.name} — {self.get_duration_display()}'

    def get_features_list(self):
        return [f.strip() for f in self.features.splitlines() if f.strip()]

    @property
    def duration_days(self):
        return self.DURATION_DAYS.get(self.duration, 30)


class PremiumSubscription(models.Model):
    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='premium_subscriptions', verbose_name='کاربر')
    plan        = models.ForeignKey(PremiumPlan, on_delete=models.SET_NULL, null=True, verbose_name='پلن')
    start_date  = models.DateTimeField(default=timezone.now, verbose_name='شروع')
    end_date    = models.DateTimeField(verbose_name='پایان')
    is_active   = models.BooleanField(default=True, verbose_name='فعال')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='assigned_premiums', verbose_name='تخصیص‌دهنده')
    note        = models.CharField(max_length=300, blank=True, verbose_name='یادداشت')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'اشتراک پریمیوم'
        verbose_name_plural = 'اشتراک‌های پریمیوم'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} — {self.plan}'

    @property
    def is_expired(self):
        return timezone.now() > self.end_date


# ═══════════════════════════════════════════════════════════════
#  PROFILE VIEW TRACKING
# ═══════════════════════════════════════════════════════════════

class ProfileView(models.Model):
    """ثبت هر بازدید از پروفایل — برای همه کاربران (پریمیوم و غیرپریمیوم)"""
    viewer      = models.ForeignKey(User, on_delete=models.CASCADE,
                                    related_name='profile_views_given',
                                    verbose_name='بازدیدکننده')
    viewed_user = models.ForeignKey(User, on_delete=models.CASCADE,
                                    related_name='profile_views_received',
                                    verbose_name='صاحب پروفایل')
    viewed_at   = models.DateTimeField(default=timezone.now, verbose_name='زمان بازدید')
    notified    = models.BooleanField(default=False, verbose_name='نوتیف ارسال شد')

    class Meta:
        verbose_name        = 'بازدید پروفایل'
        verbose_name_plural = 'بازدیدهای پروفایل'
        ordering            = ['-viewed_at']
        indexes             = [
            models.Index(fields=['viewed_user', 'viewed_at']),
            models.Index(fields=['viewer', 'viewed_user']),
        ]

    def __str__(self):
        return f'{self.viewer.username} → {self.viewed_user.username} @ {self.viewed_at:%Y-%m-%d %H:%M}'


# ════════════════════════════════════════════════════════
#  🎯  ماموریت‌های روزانه
# ════════════════════════════════════════════════════════

# مبدأ ثابت برای محاسبه‌ی چرخه — تغییرش نده وگرنه ترتیب چرخه جابه‌جا می‌شود.
MISSION_CYCLE_EPOCH = datetime.date(2024, 1, 1)


class MissionDay(models.Model):
    """یک روز در چرخه‌ی ماموریت‌های روزانه.
    روزها به‌ترتیب day_number و به‌صورت چرخشی نمایش داده می‌شوند:
    وقتی به آخرین روز رسید، دوباره از روز اول شروع می‌شود."""
    day_number = models.PositiveSmallIntegerField(verbose_name='شماره روز در چرخه')
    label      = models.CharField(max_length=60, blank=True, verbose_name='عنوان روز')
    is_active  = models.BooleanField(default=True, verbose_name='فعال')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['day_number', 'id']
        verbose_name = 'روز ماموریت'
        verbose_name_plural = 'روزهای چرخه‌ی ماموریت'

    def __str__(self):
        return self.label or f'روز {self.day_number}'

    @classmethod
    def active_cycle(cls):
        """لیست روزهای فعال به‌ترتیب چرخه."""
        return list(cls.objects.filter(is_active=True).order_by('day_number', 'id'))

    @classmethod
    def current(cls):
        """روزِ امروزِ چرخه را برمی‌گرداند (یا None اگر هیچ روزی تعریف نشده)."""
        days = cls.active_cycle()
        if not days:
            return None
        idx = (timezone.localdate() - MISSION_CYCLE_EPOCH).days % len(days)
        return days[idx]

    @property
    def cycle_position(self):
        """شماره‌ی این روز در چرخه (۱-based) و طول کل چرخه."""
        days = MissionDay.active_cycle()
        total = len(days)
        try:
            pos = days.index(self) + 1
        except ValueError:
            pos = self.day_number
        return pos, total


class DailyMission(models.Model):
    """تعریف یک ماموریت روزانه — در ادمین قابل تنظیم."""
    EVENT_LOGIN    = 'login'
    EVENT_POST     = 'post'
    EVENT_COMMENT  = 'comment'
    EVENT_FOLLOW   = 'follow'
    EVENT_LFG_JOIN = 'lfg_join'
    EVENT_REACT    = 'react'
    EVENT_CHOICES = [
        (EVENT_LOGIN,    'ورود روزانه'),
        (EVENT_POST,     'انتشار پست'),
        (EVENT_COMMENT,  'ارسال کامنت'),
        (EVENT_FOLLOW,   'دنبال کردن گیمر'),
        (EVENT_LFG_JOIN, 'پیوستن به LFG'),
        (EVENT_REACT,    'واکنش به پست'),
    ]

    day           = models.ForeignKey(
        'MissionDay', null=True, blank=True, on_delete=models.CASCADE,
        related_name='missions', verbose_name='روز چرخه (خالی = همیشگی)',
    )
    title         = models.CharField(max_length=100, verbose_name='عنوان ماموریت')
    description   = models.CharField(max_length=200, blank=True, verbose_name='توضیح')
    event         = models.CharField(max_length=20, choices=EVENT_CHOICES, verbose_name='رویداد')
    target_count  = models.PositiveSmallIntegerField(default=1, verbose_name='تعداد هدف')
    reward_zarban = models.PositiveIntegerField(default=10, verbose_name='جایزه (ضربان)')
    icon          = models.CharField(max_length=40, default='bi-check-circle-fill', verbose_name='آیکون')
    is_active     = models.BooleanField(default=True, verbose_name='فعال')
    order         = models.PositiveSmallIntegerField(default=0, verbose_name='ترتیب نمایش')
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'ماموریت روزانه'
        verbose_name_plural = 'ماموریت‌های روزانه'

    def __str__(self):
        return f'{self.title} ({self.get_event_display()} ×{self.target_count})'


class DailyMissionProgress(models.Model):
    """پیشرفت یک کاربر در یک ماموریت در یک روز مشخص."""
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mission_progress')
    mission    = models.ForeignKey(DailyMission, on_delete=models.CASCADE, related_name='progress')
    date       = models.DateField(verbose_name='تاریخ')
    progress   = models.PositiveSmallIntegerField(default=0, verbose_name='پیشرفت')
    claimed    = models.BooleanField(default=False, verbose_name='جایزه گرفته شده')
    claimed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('user', 'mission', 'date')]
        ordering = ['-date']
        verbose_name = 'پیشرفت ماموریت'
        verbose_name_plural = 'پیشرفت ماموریت‌ها'
        indexes = [models.Index(fields=['user', 'date'])]

    def __str__(self):
        return f'{self.user.username} | {self.mission.title} | {self.date}'

    @property
    def is_complete(self):
        return self.progress >= self.mission.target_count
