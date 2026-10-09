"""
Django settings for library_portal project.
Configured for local development and Render deployment.
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/stable/howto/deployment/checklist/

# SECRET_KEY: Loaded from environment in production, safe fallback in local dev
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if os.environ.get("RENDER") == "True" or os.environ.get("DEBUG", "").lower() == "false":
        raise ValueError("SECRET_KEY environment variable must be set in production.")
    SECRET_KEY = "django-insecure-local-dev-fallback-key-library-portal-demo"

# DEBUG is True locally, False when deployed or when explicitly set
if "DEBUG" in os.environ:
    DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "yes")
else:
    DEBUG = os.environ.get("RENDER", "False") != "True"

ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".onrender.com", "testserver"]
render_external_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if render_external_hostname:
    ALLOWED_HOSTS.append(render_external_hostname)

CSRF_TRUSTED_ORIGINS = [
    "https://*.onrender.com",
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
# Using SQLite as required by assignment specification (Phase 2 & Phase 15)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
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

# Email Configuration (Environment configurable for Password Reset flow)
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend'
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'Digital Library Portal <noreply@digitallibrary.portal>')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
