"""
Django settings for library_portal project.
Configured for local development and Render deployment.
"""

import os
from pathlib import Path

import secrets

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load local .env if present (never committed to git)
_env_file = BASE_DIR / '.env'
if _env_file.exists():
    try:
        with open(_env_file, 'r', encoding='utf-8') as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith('#') and '=' in _line:
                    _k, _v = _line.split('=', 1)
                    os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
    except Exception:
        pass

# SECRET_KEY: Loaded from environment or .env; fallback to persistent local key in development
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if os.environ.get("RENDER") == "True" or os.environ.get("DEBUG", "").lower() == "false":
        raise ValueError("SECRET_KEY environment variable must be set in production.")
    # In local development without SECRET_KEY in environment or .env,
    # preserve a stable key across restarts so user login sessions do not invalidate
    _secret_file = BASE_DIR / '.local_secret_key'
    if _secret_file.exists():
        try:
            SECRET_KEY = _secret_file.read_text(encoding='utf-8').strip()
        except Exception:
            SECRET_KEY = ""
    if not SECRET_KEY:
        SECRET_KEY = secrets.token_urlsafe(50)
        try:
            _secret_file.write_text(SECRET_KEY, encoding='utf-8')
        except Exception:
            pass

# DEBUG is True locally, False when deployed or when explicitly set
if "DEBUG" in os.environ:
    DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "yes")
else:
    DEBUG = os.environ.get("RENDER", "False") != "True"

from decimal import Decimal

# Daily overdue fine rate: configurable in settings/env (Default: ₹5.00 per day)
DAILY_FINE_RATE = Decimal(os.environ.get('DAILY_FINE_RATE', '5.00'))

ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".onrender.com", "digital-library-portal.onrender.com", "testserver"]
render_external_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if render_external_hostname and render_external_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_external_hostname)

CSRF_TRUSTED_ORIGINS = [
    "https://*.onrender.com",
    "https://digital-library-portal.onrender.com",
]
if render_external_hostname:
    CSRF_TRUSTED_ORIGINS.append(f"https://{render_external_hostname}")

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Custom apps
    'circulation',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'library_portal.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'library_portal.wsgi.application'

# Database
# Using SQLite with persistent storage support for local and Render deployments
_db_env_path = os.environ.get('SQLITE_DB_PATH')
if _db_env_path:
    DB_PATH = Path(_db_env_path)
elif os.environ.get('RENDER') == 'True' and Path('/var/data').is_dir():
    DB_PATH = Path('/var/data/db.sqlite3')
else:
    DB_PATH = BASE_DIR / 'db.sqlite3'

# Ensure the database parent directory exists if using a custom mount path
try:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DB_PATH,
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Whitenoise storage configuration for production caching (Django 5+ / 6+)
if DEBUG:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

# Authentication Redirects
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'student_dashboard'
LOGOUT_REDIRECT_URL = 'catalog'

# Session Persistence Settings (Prevents premature logout across server restarts)
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 1209600  # 14 days in seconds
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = False

# Email Configuration (Environment configurable for Password Reset flow)
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend'
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_TIMEOUT = 10
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'Digital Library Portal <noreply@digitallibrary.portal>')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Application Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'circulation': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}
