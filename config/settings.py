
"""
Django settings for config project.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from the repository root
load_dotenv(BASE_DIR / ".env")


# Security settings
DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() == "true"

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if DEBUG:
    SECRET_KEY = SECRET_KEY or "local-development-only-insecure-secret"
elif len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 16:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be externally supplied and contain at least "
        "50 characters with at least 16 distinct characters when "
        "DJANGO_DEBUG is False."
    )

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost"
    ).split(",")
    if host.strip()
]


# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
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

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.user_role",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# SQLite keeps local setup and CI self-contained; set DB_ENGINE=mysql for production.
if os.getenv("DB_ENGINE", "sqlite").lower() == "mysql":
    DATABASES = {"default": {"ENGINE": "django.db.backends.mysql", "NAME": os.getenv("DB_NAME", "hms_db"), "USER": os.getenv("DB_USER", "root"), "PASSWORD": os.getenv("DB_PASSWORD", ""), "HOST": os.getenv("DB_HOST", "127.0.0.1"), "PORT": os.getenv("DB_PORT", "3306"), "OPTIONS": {"charset": "utf8mb4"}}}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": Path(
                os.getenv("SQLITE_DB_PATH", str(BASE_DIR / "db.sqlite3"))
            ).expanduser().resolve(),
        }
    }


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# Internationalization
LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Secure defaults for production. Local development can opt out with DJANGO_DEBUG=true.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SECURE = (
    not DEBUG or os.getenv("DJANGO_COOKIE_SECURE", "False").lower() == "true"
)
CSRF_COOKIE_SECURE = (
    not DEBUG or os.getenv("DJANGO_COOKIE_SECURE", "False").lower() == "true"
)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = (
    os.getenv("DJANGO_HSTS_INCLUDE_SUBDOMAINS", "False").lower() == "true"
)
SECURE_HSTS_PRELOAD = os.getenv("DJANGO_HSTS_PRELOAD", "False").lower() == "true"
SECURE_SSL_REDIRECT = (
    not DEBUG
    or os.getenv("DJANGO_SECURE_SSL_REDIRECT", "False").lower() == "true"
)
TRUST_PROXY_HEADERS = (
    os.getenv("DJANGO_TRUST_PROXY_SSL_HEADER", "False").lower() == "true"
)
SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https") if TRUST_PROXY_HEADERS else None
)
USE_X_FORWARDED_HOST = TRUST_PROXY_HEADERS


# Email configuration: console backend for development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"
