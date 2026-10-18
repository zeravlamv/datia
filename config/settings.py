import os
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

# 1. Environment Setup
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))
SECRET_KEY = env('SECRET_KEY', default='django-insecure-strict-mode-v2')
DEBUG = env.bool('DEBUG', default=False)
#ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['127.0.0.1', 'localhost'])
ALLOWED_HOSTS = ['*']
DATIA_LOG_FILE = env('DATIA_LOG_FILE', default=None)

# CSRF Configuration for Mobile/Tunnel Access
CSRF_TRUSTED_ORIGINS = [
    'https://*.trycloudflare.com',
    'https://*.ngrok-free.app',
    'https://*.ngrok-free.dev',
    'https://*.localtunnel.me',
    'https://localhost',
    'http://localhost',
    'http://127.0.0.1',
]

# Fix for Ngrok/Cloudflare SSL Termination (CSRF 403)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# 3. Application Definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'ninja',
    # Local
    'datia',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware', # [NEW] I18n
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Custom
    'datia.middleware.TraceIDMiddleware', 
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# 4. Database (PostgreSQL único - simplificado)
# MSSQL solo se usa para consulta directa via pyodbc (ETLService)
DATABASES = {
    'default': env.db('DATIA_ANALYTICS_URL', default='postgres://postgres@localhost:5432/datia'),
    # Alias para compatibilidad con código existente
    'analytics': env.db('DATIA_ANALYTICS_URL', default='postgres://postgres@localhost:5432/datia')
}

# Router eliminado - todo en PostgreSQL ahora
# DATABASE_ROUTERS = ['datia.routers.DatiaRouter']  # ← DISABLED

# 5. Logging (Structured JSON + TraceID)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s %(trace_id)s',
        },
        'verbose': {
            'format': '{levelname} {asctime} {module} {message} [TraceID: {trace_id}]',
            'style': '{',
        },
    },
    'filters': {
        'trace_id': {
            '()': 'datia.middleware.TraceIDFilter',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'filters': ['trace_id'],
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': DATIA_LOG_FILE or 'datia.log',
            'formatter': 'json',
            'filters': ['trace_id'],
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'datia': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# 6. Internationalization
# 6. Internationalization
LANGUAGE_CODE = 'es'
LANGUAGES = [
    ('es', 'Español'),
    ('en', 'English'),
    ('fr', 'Français'),
    ('pt', 'Português'),
    ('it', 'Italiano'),
    ('de', 'Deutsch'),
    ('ca', 'Català'),
    ('eu', 'Euskara'),
    ('gl', 'Galego'),
]
LOCALE_PATHS = [
    BASE_DIR / 'locale',
]
TIME_ZONE = 'Europe/Madrid'
USE_I18N = True
USE_TZ = True

# 7. Static files
STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'datia_pro',
]

# 8. Datia Specific Config
DATIA_RATE_LIMIT = env('DATIA_RATE_LIMIT', default='100/m')
DATIA_AI_PROVIDER = env('DATIA_AI_PROVIDER', default=None)
DATIA_AI_CONTEXT_DIR = env('DATIA_AI_CONTEXT_DIR', default=str(BASE_DIR))

# 9. MSSQL Config (From Env)
MSSQL_DRIVER = env('MSSQL_DRIVER', default='{ODBC Driver 17 for SQL Server}')
MSSQL_HOST = env('MSSQL_HOST', default='localhost')
MSSQL_PORT = env('MSSQL_PORT', default='1433')
MSSQL_USER = env('MSSQL_USER', default='sa')
MSSQL_PASSWORD = env('MSSQL_PASSWORD', default='')
MSSQL_NAME = env('MSSQL_NAME', default='master')

# 10. Authentication
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'comercial'
