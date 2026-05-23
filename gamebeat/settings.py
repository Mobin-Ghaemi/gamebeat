from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Security ────────────────────────────────────────────────────
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-4vu-)f996y3#n3s)ek4t_4tamz%48z&)uvy6*1#uade8imv44v'
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get(
    'DJANGO_ALLOWED_HOSTS', 'localhost 127.0.0.1'
).split()

# ── Apps ────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'account',
    'gamenet',
    'community',
    'dashboard',
]

# ── Middleware ───────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   # static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'gamebeat.main_urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'account/templates',
            BASE_DIR / 'gamenet/templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'gamebeat.wsgi.application'

# ── Database ─────────────────────────────────────────────────────
# روی لیارا: disk به /app/db mount میشه — db.sqlite3 اونجا نگه داریم
DB_DIR = Path(os.environ.get('DB_DIR', str(BASE_DIR)))
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DB_DIR / 'db.sqlite3',
    }
}

# ── Password validation ──────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Internationalisation ─────────────────────────────────────────
LANGUAGE_CODE = 'fa-ir'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_L10N = True
USE_TZ = True
USE_THOUSAND_SEPARATOR = True
THOUSAND_SEPARATOR = ','
NUMBER_GROUPING = 3

# ── Static & Media ───────────────────────────────────────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ── Auth ─────────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/account/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/account/login/'
