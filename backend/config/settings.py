import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-only-change-before-deploy')
DEBUG = os.getenv('DEBUG', 'true').lower() == 'true'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
INSTALLED_APPS = ['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','rest_framework','rest_framework_simplejwt.token_blacklist','corsheaders','payroll']
MIDDLEWARE = ['corsheaders.middleware.CorsMiddleware','django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF='config.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION='config.wsgi.application'
DB_ENGINE=os.getenv('DB_ENGINE','django.db.backends.postgresql')
if DB_ENGINE == 'django.db.backends.sqlite3': DATABASES={'default':{'ENGINE':DB_ENGINE,'NAME':BASE_DIR/'db.sqlite3'}}
else: DATABASES={'default':{'ENGINE':DB_ENGINE,'NAME':os.getenv('DB_NAME','epms'),'USER':os.getenv('DB_USER','epms_user'),'PASSWORD':os.getenv('DB_PASSWORD','change-me'),'HOST':os.getenv('DB_HOST','localhost'),'PORT':os.getenv('DB_PORT','5432'),'CONN_MAX_AGE':60}}
AUTH_USER_MODEL='payroll.User'
AUTH_PASSWORD_VALIDATORS=[{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'}]
LANGUAGE_CODE='en-us'; TIME_ZONE='Asia/Kolkata'; USE_I18N=True; USE_TZ=True
STATIC_URL='static/'; DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
CORS_ALLOWED_ORIGINS=os.getenv('CORS_ALLOWED_ORIGINS','http://localhost:8000').split(',')
REST_FRAMEWORK={'DEFAULT_AUTHENTICATION_CLASSES':('rest_framework_simplejwt.authentication.JWTAuthentication',),'DEFAULT_PERMISSION_CLASSES':('payroll.permissions.IsCompanyUser',),'DEFAULT_THROTTLE_RATES':{'login':'10/minute'}}
SIMPLE_JWT={'ACCESS_TOKEN_LIFETIME':timedelta(minutes=20),'REFRESH_TOKEN_LIFETIME':timedelta(days=1),'ROTATE_REFRESH_TOKENS':True,'BLACKLIST_AFTER_ROTATION':True}

EMAIL_BACKEND=os.getenv('EMAIL_BACKEND','django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST=os.getenv('EMAIL_HOST','localhost'); EMAIL_PORT=int(os.getenv('EMAIL_PORT','587')); EMAIL_HOST_USER=os.getenv('EMAIL_HOST_USER',''); EMAIL_HOST_PASSWORD=os.getenv('EMAIL_HOST_PASSWORD',''); EMAIL_USE_TLS=os.getenv('EMAIL_USE_TLS','true').lower()=='true'; DEFAULT_FROM_EMAIL=os.getenv('DEFAULT_FROM_EMAIL','noreply@epms.local')
MEDIA_URL='/media/'; MEDIA_ROOT=BASE_DIR/'media'
