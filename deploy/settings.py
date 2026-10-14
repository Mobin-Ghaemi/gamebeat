import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = Path(os.environ['DJANGO_SECRET_KEY_FILE']).read_text().strip()
DEBUG = False
ALLOWED_HOSTS = os.environ['DJANGO_ALLOWED_HOSTS'].split(',')
INSTALLED_APPS = ['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','account','community','dashboard','gamenet']
MIDDLEWARE = ['deploy.middleware.HealthCheckMiddleware','django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware','community.middleware.JsonErrorTranslationMiddleware','community.middleware.OnlineTrackingMiddleware','community.middleware.PageViewMiddleware']
ROOT_URLCONF = 'deploy.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages','community.context_processors.nav_badges','community.context_processors.seo_defaults']}}]
WSGI_APPLICATION = 'deploy.wsgi.application'
DATABASES = {'default':{'ENGINE':'django.db.backends.postgresql','NAME':'gamebeat','USER':'gamebeat','PASSWORD':Path(os.environ['DB_PASSWORD_FILE']).read_text().strip(),'HOST':os.environ.get('DB_HOST','db'),'PORT':'5432','CONN_MAX_AGE':60,'CONN_HEALTH_CHECKS':True,'OPTIONS':{'connect_timeout':5}}}
if os.getenv('IMPORT_SQLITE'):
    DATABASES = {'default':{'ENGINE':'django.db.backends.sqlite3','NAME':os.environ['IMPORT_SQLITE']}}
AUTH_PASSWORD_VALIDATORS = [{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE = 'fa-ir'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR/'staticfiles'
STATICFILES_DIRS = [BASE_DIR/'static']
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR/'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/account/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/account/login/'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO','https')
CSRF_TRUSTED_ORIGINS = os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS','').split(',')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
