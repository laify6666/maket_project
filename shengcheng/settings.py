"""
Django settings for shengcheng project.

The project targets Django 4.2+ and keeps development-friendly defaults while
allowing production values to be supplied through environment variables.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    # Keep the project runnable when python-dotenv is not installed.
    load_dotenv = lambda *args, **kwargs: None

BASE_DIR = Path(__file__).resolve().parent.parent

# Optional local overrides for secret keys, debug flag, hosts, etc.
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=None):
    value = os.getenv(name)
    if not value:
        return default or []
    return [item.strip() for item in value.split(",") if item.strip()]


# SECURITY WARNING: keep the secret key used in production secret.
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "dev-only-insecure-secret-change-me-before-deploying",
)

# SECURITY WARNING: don't run with debug turned on in production.
DEBUG = env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    ["localhost", "127.0.0.1", "testserver"],
)


# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "buy",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "shengcheng.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "buy" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "shengcheng.wsgi.application"
ASGI_APPLICATION = "shengcheng.asgi.application"


# Database
DATABASES = {
    "default": {
        "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.getenv("DB_NAME", BASE_DIR / "db.sqlite3"),
        "USER": os.getenv("DB_USER", ""),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", ""),
        "PORT": os.getenv("DB_PORT", ""),
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Custom user model
AUTH_USER_MODEL = "buy.User"


# Internationalization
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATICFILES_DIRS = [
    BASE_DIR / "buy" / "static",
    BASE_DIR / "static",
]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Uploaded goods images are served from /media/, never mixed into static.
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024


# Auth and session
LOGIN_URL = "/denglu/"
LOGIN_REDIRECT_URL = "/"
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 3600 * 24
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False


# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Production hardening is only enabled outside DEBUG.
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "buy": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
