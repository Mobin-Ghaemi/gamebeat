# GameBeat — Context کامل پروژه برای چت جدید

## اطلاعات کلی پروژه

- **نوع:** پروژه Django — شبکه اجتماعی گیمرها
- **نام پروژه:** GameBeat
- **مسیر:** `/Users/mobinghaemi/Desktop/gamebeat`
- **دیتابیس:** SQLite (`db.sqlite3`)
- **زبان رابط:** فارسی (RTL)
- **Python:** 3.x / Django 4.x
- **URL اصلی:** `http://localhost:8000`
- **پنل ادمین:** `http://localhost:8000/admin-panel/`

---

## ساختار App‌ها

```
gamebeat/           ← تنظیمات اصلی (settings.py, main_urls.py)
account/            ← ثبت‌نام / ورود / خروج کاربران
community/          ← فید اجتماعی، پست، کامنت، هشتگ، پروفایل، DM، notif
dashboard/          ← پنل ادمین سفارشی (نه Django Admin)
gamenet/            ← بخش‌های مربوط به بازی‌ها (جداگانه)
game/               ← (خالی / قدیمی)
chalenge/           ← (خالی / قدیمی)
trading/            ← (خالی / قدیمی)
```

---

## URL‌های اصلی (main_urls.py)

```python
path("admin/",        admin.site.urls)           # Django admin
path("",              include("community.urls"))  # فید اصلی
path("account/",      include("account.urls"))    # لاگین/رجیستر
path("gamenet/",      include("gamenet.urls"))
path("admin-panel/",  include("dashboard.urls"))  # پنل ادمین سفارشی
```

---

## community/urls.py (وضعیت فعلی — کامل)

```python
from django.urls import path
from . import views

app_name = 'community'

urlpatterns = [
    path('', views.feed, name='feed'),
    path('search/', views.search_gamers, name='search'),
    path('lfg/', views.lfg_board, name='lfg'),
    path('lfg/create/', views.create_lfg, name='create_lfg'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('post/create/', views.create_post, name='create_post'),
    path('post/<int:post_id>/like/', views.toggle_like, name='toggle_like'),
    path('post/<int:post_id>/comment/', views.add_comment, name='add_comment'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/me/', views.my_profile_dashboard, name='my_profile'),
    path('profile/<str:username>/', views.gamer_profile, name='profile'),
    path('follow/<str:username>/', views.toggle_follow, name='toggle_follow'),
    path('post/<int:post_id>/delete/', views.delete_post, name='delete_post'),
    path('gaming/connect/', views.connect_gaming_account, name='connect_gaming'),
    path('gaming/disconnect/', views.disconnect_gaming_account, name='disconnect_gaming'),
    path('post/new/', views.create_post_page, name='create_post_page'),
    path('api/hashtags/', views.hashtag_suggest, name='hashtag_suggest'),
    path('api/link-preview/', views.link_preview, name='link_preview'),
    path('hashtag/<str:tag_name>/', views.hashtag_feed, name='hashtag_feed'),
    path('post/<int:post_id>/react/', views.react_post, name='react_post'),
    path('post/<int:post_id>/reactions/', views.get_post_reactions, name='post_reactions'),
    path('steam/fetch/', views.steam_fetch, name='steam_fetch'),
    path('steam/search/', views.steam_search, name='steam_search'),
    path('backlog/add/', views.backlog_add, name='backlog_add'),
    path('backlog/<int:item_id>/update/', views.backlog_update, name='backlog_update'),
    path('backlog/<int:item_id>/remove/', views.backlog_remove, name='backlog_remove'),
    path('backlog/<int:item_id>/favorite/', views.backlog_toggle_favorite, name='backlog_favorite'),
    path('backlog/<str:username>/', views.backlog_list, name='backlog_list'),
    path('games/', views.games_ranking, name='games_ranking'),
    path('notifications/', views.notifications_list, name='notifications'),
    path('api/notifications/count/', views.notifications_count, name='notifications_count'),
    path('inbox/', views.inbox, name='inbox'),
    path('dm/<str:username>/', views.conversation, name='conversation'),
    path('dm/<str:username>/send/', views.send_message_ajax, name='send_message'),
    path('api/inbox/count/', views.inbox_unread_count, name='inbox_count'),
]
```

> ⚠️ مهم: `translate_to_fa` از views حذف شده بود اما URL داشت — URL حذف شد. اگه دوباره اضافه بشه باید view هم داشته باشه.

---

## dashboard/urls.py (وضعیت فعلی — کامل)

```python
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_index, name='index'),
    path('users/', views.user_list, name='users'),
    path('users/<int:user_id>/ban/', views.user_toggle_ban, name='user_ban'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('posts/', views.post_list, name='posts'),
    path('posts/bulk-delete/', views.post_bulk_delete, name='post_bulk_delete'),
    path('posts/<int:pk>/approve/', views.post_approve, name='post_approve'),
    path('posts/<int:post_id>/delete/', views.post_delete, name='post_delete'),
    path('posts/<int:post_id>/', views.post_detail, name='post_detail'),
    path('comments/', views.comment_list, name='comments'),
    path('comments/bulk-delete/', views.comment_bulk_delete, name='comment_bulk_delete'),
    path('comments/<int:pk>/approve/', views.comment_approve, name='comment_approve'),
    path('comments/<int:comment_id>/delete/', views.comment_delete, name='comment_delete'),
    path('hashtags/', views.hashtag_list, name='hashtags'),
    path('hashtags/<int:pk>/approve/', views.hashtag_approve, name='hashtag_approve'),
    path('hashtags/<int:hashtag_id>/delete/', views.hashtag_delete, name='hashtag_delete'),
    path('games/', views.game_list, name='games'),
    path('games/add/', views.game_add, name='game_add'),
    path('games/<int:game_id>/edit/', views.game_edit, name='game_edit'),
    path('games/<int:game_id>/delete/', views.game_delete, name='game_delete'),
]
```

---

## مدل‌های اصلی (community/models.py)

### Hashtag
```python
class Hashtag(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    post_count = models.PositiveIntegerField(default=0)
    is_approved = models.BooleanField(default=True)  # ← اضافه شده
    created_at = models.DateTimeField(auto_now_add=True)
```

### Post
```python
class Post(models.Model):
    POST_TYPES = [('text','متن'),('achievement','دستاورد'),
                  ('lfg','جستجوی تیم'),('highlight','هایلایت'),
                  ('image','تصویر'),('link','لینک')]
    author = ForeignKey(User, related_name='posts')
    content = TextField()
    image = ImageField(upload_to='community/posts/', blank=True, null=True)
    video = FileField(upload_to='community/posts/videos/', blank=True, null=True)
    post_type = CharField(max_length=15, choices=POST_TYPES, default='text')
    game_tag = CharField(max_length=100, blank=True)
    is_public = BooleanField(default=True)
    is_approved = BooleanField(default=True)  # ← اضافه شده
    hashtags = ManبyToManyField('Hashtag', blank=True, related_name='posts')
    link_url / link_title / link_description / link_image_url = ...
    created_at / updated_at = ...
```

### Comment
```python
class Comment(models.Model):
    post = ForeignKey(Post, related_name='comments')
    author = ForeignKey(User)
    content = TextField(max_length=500)
    is_approved = BooleanField(default=True)  # ← اضافه شده
    created_at = DateTimeField(auto_now_add=True)
```

### سایر مدل‌های مهم
- `GamerProfile` — پروفایل کاربر، platforms (JSONField)، bio، avatar، banner، xp، level
- `Follow` — رابطه فالو بین کاربران
- `PostLike` — لایک پست
- `PostReaction` — ری‌اکشن (🔥💀😤👑😂)
- `GameBacklog` — بک‌لاگ بازی کاربر (want/playing/completed/dropped)
- `Notification` — اعلان (like/comment/follow/mention)
- `Conversation` + `Message` — پیام خصوصی
- `GamingAccount` — اتصال به Steam/Xbox/PSN/...
- `LFGPost` — پیدا کردن همبازی

---

## سیستم مدیریت محتوا (Moderation) — تازه پیاده شده

### منطق کلی
- پست/کامنت/هشتگ جدید → `is_approved=False` ذخیره می‌شن
- در سایت برای کاربران **نمایش داده می‌شن** (فیلتر `is_public=True` هست، نه `is_approved`)
- در پنل ادمین → تب «در انتظار» و «بررسی شده» برای هر بخش
- ادمین می‌تونه تأیید یا حذف کنه

### Migrations اعمال شده
```
community 0011_add_is_approved      ← فیلد is_approved به 3 مدل
community 0012_merge_...            ← merge با 0011_backlog_game_fk
```

### Views پنل ادمین
| View | URL | کار |
|------|-----|-----|
| `post_list` | `posts/?tab=pending` یا `?tab=approved` | لیست پست‌ها با تب‌بندی |
| `post_approve` | `posts/<pk>/approve/` | تأیید پست |
| `comment_list` | `comments/?tab=pending` | لیست کامنت‌ها |
| `comment_approve` | `comments/<pk>/approve/` | تأیید کامنت |
| `hashtag_list` | `hashtags/` | لیست + فرم ساخت هشتگ (POST روی همین URL) |
| `hashtag_approve` | `hashtags/<pk>/approve/` | تأیید هشتگ |

---

## Steam Import بازی (در پنل ادمین)

- صفحه افزودن بازی → سرچ در Steam → کلیک روی نتیجه → فرم پر می‌شه
- **API:** `store.steampowered.com/api/appdetails` و `storesearch`
- برمی‌گردونه: name, cover_url, description, release_date, genres
- **Wikidata** هم برای پلتفرم‌های کنسول استفاده می‌شه (P1733=Steam AppID)

---

## باگ‌های مهم که قبلاً حل شدن

### 1. Platform Checkbox در فرم ویرایش
- **مشکل:** نمی‌شد تیک زد
- **علت:** selector `.platform-label` روی genre label هم match می‌کرد → TypeError → crash
- **Fix:** `.platform-label:not(.genre-label)` + `e.preventDefault()` + null guard

### 2. ژانر فقط یک آیتم نشون می‌داد
- **علت:** `break` بعد از اول match
- **Fix:** حذف `break`، collect همه ژانرها

### 3. NoReverseMatch برای hashtag_add
- **علت ۱:** `.pyc` cache قدیمی — Fix: `find . -name "*.pyc" -delete`
- **علت ۲:** `community/urls.py` به `translate_to_fa` رجوع می‌کرد که در views نبود
- **Fix:** URL مرده حذف، `hashtag_add` داخل `hashtag_list` ادغام شد

---

## settings.py — نکات مهم

```python
LANGUAGE_CODE = 'fa-ir'
TIME_ZONE = 'Asia/Tehran'
USE_TZ = True
ROOT_URLCONF = 'gamebeat.main_urls'  # نه urls.py
LOGIN_URL = '/account/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/account/login/'
MEDIA_ROOT = BASE_DIR / 'media'
STATIC_ROOT = BASE_DIR / 'staticfiles'
```

---

## دستورات رایج

```bash
# اجرای سرور
cd /Users/mobinghaemi/Desktop/gamebeat
python manage.py runserver

# بررسی سلامت پروژه
python manage.py check

# اعمال migration جدید
python manage.py makemigrations
python manage.py migrate

# پاک کردن کش Python (وقتی URL عجیب بود)
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +
```

---

## نکات مهم برای چت جدید

1. **پنل ادمین سفارشی است** — نه `django.contrib.admin`. فایل‌های dashboard/ هستن.
2. **is_admin چک می‌کنه** `user.is_staff or user.is_superuser`
3. **فارسی RTL** — تمپلیت‌ها راست به چپ هستن
4. **هر بار که URL جدید اضافه می‌کنی** باید هم در `urls.py` باشه هم view تعریف شده باشه، وگرنه کل URL resolver خراب می‌شه
5. **هر بار که migration جدید می‌زنی** باید `python manage.py migrate` اجرا بشه
6. **اگه چند migration با یه شماره بود** — `python manage.py makemigrations --merge --no-input`
