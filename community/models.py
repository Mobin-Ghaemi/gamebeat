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
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='gamer_profile', verbose_name='کاربر')
    bio = models.TextField(max_length=500, blank=True, verbose_name='درباره من')
    avatar = models.ImageField(upload_to='community/avatars/', blank=True, null=True, verbose_name='آواتار')
    banner = models.ImageField(upload_to='community/banners/', blank=True, null=True, verbose_name='بنر پروفایل')
    city = models.CharField(max_length=20, choices=CITY_CHOICES, blank=True, verbose_name='شهر')
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES, default='pc', verbose_name='پلتفرم اصلی')
    platforms = models.JSONField(default=list, blank=True, verbose_name='پلتفرم‌ها')
    gaming_style = models.CharField(max_length=20, choices=GAMING_STYLE_CHOICES, blank=True, verbose_name='سبک بازی')
    rank = models.CharField(max_length=15, choices=RANK_CHOICES, blank=True, verbose_name='رنک')
    favorite_games = models.TextField(blank=True, verbose_name='بازی‌های مورد علاقه')
    steam_id = models.CharField(max_length=100, blank=True, verbose_name='Steam ID')
    psn_id = models.CharField(max_length=100, blank=True, verbose_name='PSN ID')
    xbox_gamertag = models.CharField(max_length=100, blank=True, verbose_name='Xbox Gamertag')
    total_hours_played = models.PositiveIntegerField(default=0, verbose_name='ساعت بازی')
    level = models.PositiveIntegerField(default=1, verbose_name='لول')
    xp = models.PositiveIntegerField(default=0, verbose_name='امتیاز تجربه')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'پروفایل گیمر'
        verbose_name_plural = 'پروفایل‌های گیمران'

    def __str__(self):
        return f'@{self.user.username}'

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

    def get_platform_display_list(self):
        """Returns list of (code, display_name, icon) tuples for all platforms"""
        icons = {
            'pc': 'bi-pc-display', 'ps4': 'bi-playstation', 'ps5': 'bi-playstation',
            'xbox': 'bi-xbox', 'switch': 'bi-nintendo-switch', 'mobile': 'bi-phone', 'multi': 'bi-controller',
        }
        labels = dict(PLATFORM_CHOICES)
        return [(p, labels.get(p, p), icons.get(p, 'bi-controller')) for p in self.get_platforms_list()]

    @property
    def level_progress(self):
        xp_per_level = 100
        return (self.xp % xp_per_level)

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

    def __str__(self):
        return f'{self.follower.username} → {self.following.username}'


class Hashtag(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    post_count = models.PositiveIntegerField(default=0)
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
    hashtags = models.ManyToManyField('Hashtag', blank=True, related_name='posts')
    link_url = models.URLField(blank=True)
    link_title = models.CharField(max_length=300, blank=True)
    link_description = models.TextField(blank=True)
    link_image_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'پست'
        verbose_name_plural = 'پست‌ها'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.author.username}: {self.content[:50]}'

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

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lfg_posts', verbose_name='پست‌دهنده')
    game_name = models.CharField(max_length=100, verbose_name='نام بازی')
    game_mode = models.CharField(max_length=15, choices=GAME_MODES, default='normal', verbose_name='مود بازی')
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES, verbose_name='پلتفرم')
    skill_level = models.CharField(max_length=15, choices=SKILL_LEVELS, default='any', verbose_name='سطح مهارت')
    description = models.TextField(max_length=300, blank=True, verbose_name='توضیحات')
    max_players = models.PositiveSmallIntegerField(default=4, verbose_name='حداکثر بازیکن')
    current_players = models.PositiveSmallIntegerField(default=1, verbose_name='بازیکنان فعلی')
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

    def __str__(self):
        return f'{self.user.username} – {self.game_name} [{self.status}]'


# ═══════════════════════════════════════
#  POST REACTIONS
# ═══════════════════════════════════════

class PostReaction(models.Model):
    REACTION_CHOICES = [
        ('fire',     '🔥 خفن'),
        ('dead',     '💀 GG'),
        ('tryhard',  '😤 Tryhard'),
        ('legend',   '👑 لجند'),
        ('ggez',     '😂 GG EZ'),
    ]

    REACTION_EMOJI = {
        'fire':    '🔥',
        'dead':    '💀',
        'tryhard': '😤',
        'legend':  '👑',
        'ggez':    '😂',
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
        ('like',    'لایک پست'),
        ('comment', 'کامنت'),
        ('follow',  'فالو'),
        ('mention', 'منشن'),
    ]

    recipient   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications')
    notif_type  = models.CharField(max_length=10, choices=NOTIF_TYPES)
    post        = models.ForeignKey('Post', on_delete=models.CASCADE, null=True, blank=True)
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
        if self.notif_type == 'like':
            return f'{self.sender.username} پستت رو لایک کرد'
        elif self.notif_type == 'comment':
            return f'{self.sender.username} روی پستت کامنت گذاشت'
        elif self.notif_type == 'follow':
            return f'{self.sender.username} شروع کرد به دنبال کردنت'
        elif self.notif_type == 'mention':
            return f'{self.sender.username} تو رو منشن کرد'
        return ''

    @property
    def icon(self):
        icons = {'like': '❤️', 'comment': '💬', 'follow': '👤', 'mention': '📢'}
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
    content      = models.TextField(max_length=2000)
    is_read      = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'پیام'
        verbose_name_plural = 'پیام‌ها'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender.username}: {self.content[:40]}'
